#!/usr/bin/env python3
"""
Bluetooth speaker manager for Room Guard.

Manages Bluetooth speaker pairing, connection, and audio routing
via bluetoothctl (BlueZ CLI). Designed for A2DP audio sinks like
the JBL Flip 7.

The module follows the project's start/stop lifecycle pattern and
uses subprocess calls to bluetoothctl for maximum compatibility
with Raspberry Pi OS Bluetooth stack.

Dependencies (system):
    sudo apt install -y bluez pulseaudio pulseaudio-module-bluetooth
"""

import json
import os
import subprocess
import threading
import time

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "bluetooth.json"
)

SCAN_TIMEOUT = 15  # seconds
CONNECT_TIMEOUT = 10  # seconds


def _run_bluetoothctl(*args, timeout=10):
    """Run a bluetoothctl command and return (success, stdout)."""
    try:
        result = subprocess.run(
            ["bluetoothctl"] + list(args),
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except FileNotFoundError:
        return False, "bluetoothctl not found — install bluez"
    except Exception as e:
        return False, str(e)


class BluetoothSpeaker:
    """
    Bluetooth speaker controller using BlueZ/bluetoothctl.

    Call start() to initialize, stop() to clean up.
    Persists the last connected device to config/bluetooth.json
    for auto-reconnect on startup.
    """

    def __init__(self, config_path=None):
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._connected = False
        self._paired = False
        self._device_address = None
        self._device_name = None
        self._lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        """Initialize Bluetooth controller and attempt auto-connect."""
        self._started = True
        # Unblock BT radio in case rfkill has it soft-blocked
        try:
            subprocess.run(["rfkill", "unblock", "bluetooth"],
                           capture_output=True, timeout=5)
        except Exception:
            pass
        # Ensure the BT adapter is powered on
        _run_bluetoothctl("power", "on")
        self._load_config()
        print("[Bluetooth] Started")

    def stop(self) -> None:
        """Clean up Bluetooth state."""
        self._started = False
        print("[Bluetooth] Stopped")

    def scan(self, timeout=SCAN_TIMEOUT) -> list[dict]:
        """Scan for nearby Bluetooth devices.

        Uses an interactive bluetoothctl process so the scan stays
        active for the full timeout (non-interactive mode exits
        immediately and discovers nothing).

        Returns a list of dicts: [{address, name, paired, connected}]
        """
        if not self._started:
            raise RuntimeError("BluetoothSpeaker not started. Call start() first.")

        # Run scan in an interactive bluetoothctl session so discovery
        # stays active for the full timeout period.
        try:
            proc = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            proc.stdin.write("scan on\n")
            proc.stdin.flush()
            time.sleep(timeout)
            proc.stdin.write("scan off\n")
            proc.stdin.flush()
            time.sleep(1)
            proc.stdin.write("quit\n")
            proc.stdin.flush()
            proc.wait(timeout=5)
        except Exception as e:
            print(f"[Bluetooth] Scan process error: {e}")

        # Parse device list (populated by BlueZ daemon during scan)
        success, output = _run_bluetoothctl("devices")
        if not success:
            return []

        devices = []
        for line in output.splitlines():
            # Format: "Device XX:XX:XX:XX:XX:XX Name"
            line = line.strip()
            if line.startswith("Device "):
                parts = line.split(" ", 2)
                if len(parts) >= 3:
                    address = parts[1]
                    name = parts[2]
                    paired, connected = self._get_device_flags(address)
                    devices.append({
                        "address": address,
                        "name": name,
                        "paired": paired,
                        "connected": connected,
                    })
        return devices

    def pair(self, address: str) -> bool:
        """Pair with a Bluetooth device (and trust it).

        The device must be in pairing mode. After pairing,
        automatically connects.
        """
        if not self._started:
            raise RuntimeError("BluetoothSpeaker not started. Call start() first.")

        print(f"[Bluetooth] Pairing with {address}...")

        # Trust the device first (allows auto-reconnect)
        _run_bluetoothctl("trust", address)

        success, output = _run_bluetoothctl("pair", address, timeout=CONNECT_TIMEOUT)
        if not success and "Already Exists" not in output:
            print(f"[Bluetooth] Pairing failed: {output}")
            return False

        print(f"[Bluetooth] Paired with {address}")

        # Attempt to connect after pairing
        return self.connect(address)

    def connect(self, address: str) -> bool:
        """Connect to an already-paired Bluetooth device (A2DP sink)."""
        if not self._started:
            raise RuntimeError("BluetoothSpeaker not started. Call start() first.")

        print(f"[Bluetooth] Connecting to {address}...")
        success, output = _run_bluetoothctl("connect", address, timeout=CONNECT_TIMEOUT)

        if not success and "Connected" not in output:
            print(f"[Bluetooth] Connection failed: {output}")
            with self._lock:
                self._connected = False
            return False

        # Get the device name
        name = self._get_device_name(address)

        with self._lock:
            self._connected = True
            self._paired = True
            self._device_address = address
            self._device_name = name or address

        self._save_config()
        print(f"[Bluetooth] Connected to {self._device_name}")
        return True

    def disconnect(self) -> bool:
        """Disconnect the current Bluetooth device."""
        if not self._started:
            raise RuntimeError("BluetoothSpeaker not started. Call start() first.")

        with self._lock:
            address = self._device_address

        if not address:
            return False

        success, _ = _run_bluetoothctl("disconnect", address)
        with self._lock:
            self._connected = False

        print(f"[Bluetooth] Disconnected from {address}")
        return True

    def remove(self, address: str) -> bool:
        """Remove (unpair/forget) a Bluetooth device."""
        if not self._started:
            raise RuntimeError("BluetoothSpeaker not started. Call start() first.")

        success, _ = _run_bluetoothctl("remove", address)
        with self._lock:
            if self._device_address == address:
                self._connected = False
                self._paired = False
                self._device_address = None
                self._device_name = None
                self._save_config()

        print(f"[Bluetooth] Removed {address}")
        return success

    def test_sound(self) -> bool:
        """Play a short test chime through the connected speaker.

        Generates a 0.3s 880Hz sine wave (A5 note) followed by a
        0.3s 1320Hz sine wave (E6) using paplay + sox.  Falls back
        to speaker-test if sox is unavailable.
        """
        if not self._started:
            raise RuntimeError("BluetoothSpeaker not started. Call start() first.")

        with self._lock:
            if not self._connected:
                return False

        # Try sox (generates a pleasant two-tone gling)
        try:
            subprocess.run(
                ["play", "-qn", "synth", "0.15", "sin", "880",
                 "synth", "0.15", "sin", "1318.5",
                 "synth", "0.2", "sin", "1760",
                 "gain", "-10"],
                capture_output=True, timeout=5,
            )
            print("[Bluetooth] Test sound played (sox)")
            return True
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[Bluetooth] sox play failed: {e}")

        # Fallback: speaker-test (single beep)
        try:
            subprocess.run(
                ["speaker-test", "-t", "sine", "-f", "880",
                 "-l", "1", "-p", "1"],
                capture_output=True, timeout=5,
            )
            print("[Bluetooth] Test sound played (speaker-test)")
            return True
        except Exception as e:
            print(f"[Bluetooth] Test sound failed: {e}")
            return False

    def get_status(self) -> dict:
        """Return current Bluetooth connection status."""
        with self._lock:
            return {
                "connected": self._connected,
                "paired": self._paired,
                "device_name": self._device_name,
                "device_address": self._device_address,
            }

    def auto_connect(self) -> bool:
        """Attempt to connect to the last known device from config.

        Returns True if connection succeeded, False otherwise.
        Fails silently if no saved device or device is unavailable.
        """
        if not self._started:
            raise RuntimeError("BluetoothSpeaker not started. Call start() first.")

        with self._lock:
            address = self._device_address

        if not address:
            print("[Bluetooth] No saved device for auto-connect")
            return False

        print(f"[Bluetooth] Auto-connecting to {address}...")
        return self.connect(address)

    def _get_device_flags(self, address: str) -> tuple[bool, bool]:
        """Check if a device is paired and/or connected via bluetoothctl info."""
        success, output = _run_bluetoothctl("info", address)
        if not success:
            return False, False
        paired = "Paired: yes" in output
        connected = "Connected: yes" in output
        return paired, connected

    def _get_device_name(self, address: str) -> str | None:
        """Get the friendly name of a device via bluetoothctl info."""
        success, output = _run_bluetoothctl("info", address)
        if not success:
            return None
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Name:"):
                return line.split(":", 1)[1].strip()
        return None

    def _load_config(self) -> None:
        """Load last connected device from config file."""
        try:
            with open(self._config_path, "r") as f:
                data = json.load(f)
            with self._lock:
                self._device_address = data.get("last_device_address")
                self._device_name = data.get("last_device_name")
                if self._device_address:
                    self._paired = True
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

    def _save_config(self) -> None:
        """Persist last connected device to config file (caller may hold _lock)."""
        data = {
            "last_device_address": self._device_address,
            "last_device_name": self._device_name,
        }
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            print(f"[Bluetooth] WARNING: Could not save config: {e}")
