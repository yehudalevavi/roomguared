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

        Returns a list of dicts: [{address, name, paired, connected}]
        """
        if not self._started:
            raise RuntimeError("BluetoothSpeaker not started. Call start() first.")

        # Start scanning
        _run_bluetoothctl("scan", "on")
        time.sleep(timeout)
        _run_bluetoothctl("scan", "off")

        # Parse device list
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
                    # Check paired/connected status via info
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
