#!/usr/bin/env python3
"""
NFC card reader module for Room Guard (MFRC522 via SPI).

Polls for NFC/RFID cards in a background thread and dispatches
configurable actions to the RoomGuard instance. Each card UID
maps to a specific action (arm/disarm, LED toggle, play melody, etc.).

Wiring (MFRC522 → RPi SPI0):
    SDA  → RPi Pin 24 (GPIO 8, CE0)
    SCK  → RPi Pin 23 (GPIO 11)
    MOSI → RPi Pin 19 (GPIO 10)
    MISO → RPi Pin 21 (GPIO 9)
    RST  → RPi Pin 22 (GPIO 25)
    VCC  → 3.3V (NOT 5V!)
    GND  → RPi Pin 20 (GND) — direct to Pi, not breadboard

Setup:
    1. Enable SPI: sudo raspi-config nonint do_spi 0
    2. Reboot the Pi
    3. Verify: ls /dev/spidev* (should show spidev0.0 and spidev0.1)
"""

import json
import os
import threading
import time

NFC_RST_PIN = 25  # GPIO 25 (Physical pin 22)
DEBOUNCE_SECONDS = 2.0  # Ignore same card re-taps within this window
POLL_INTERVAL = 0.3  # Seconds between card polls
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "nfc_cards.json"
)


def uid_to_hex(uid_bytes):
    """Convert a UID byte list to a hex string like '0x1A2B3C4D'."""
    return "0x" + "".join(f"{b:02X}" for b in uid_bytes)


class NFCReader:
    """
    NFC/RFID card reader using the MFRC522 module.

    Polls for cards in a background daemon thread and dispatches
    actions to a RoomGuard instance based on a configurable
    UID-to-action mapping stored in a JSON config file.
    """

    def __init__(self, guard, config_path=None):
        self._guard = guard
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._cards: list[dict] = []
        self._reader = None
        self._running = False
        self._thread = None
        self._last_uid = None
        self._last_time = 0.0
        self._last_scan: dict | None = None
        self._lock = threading.Lock()

        # Scan mode: when active, next card tap is captured instead of dispatched
        self._scan_event = threading.Event()
        self._scanned_uid: str | None = None
        self._scan_waiting = False

        self._load_config()

    def start(self) -> None:
        """Initialize the MFRC522 reader and start the polling thread."""
        from mfrc522 import SimpleMFRC522
        self._reader = SimpleMFRC522()
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the polling thread and clean up GPIO."""
        self._running = False
        if self._reader is not None:
            try:
                import RPi.GPIO as GPIO
                GPIO.cleanup()
            except Exception:
                pass
            self._reader = None

    def get_registered_cards(self) -> list[dict]:
        """Return a copy of all registered cards."""
        with self._lock:
            return list(self._cards)

    def get_last_scan(self) -> dict | None:
        """Return the last scanned card info, or None."""
        with self._lock:
            return dict(self._last_scan) if self._last_scan else None

    @property
    def is_scanning(self) -> bool:
        """True if the reader is in scan-to-register mode."""
        return not self._scan_event.is_set() and self._scanned_uid is None and self._scan_waiting

    def wait_for_scan(self, timeout: float = 15.0) -> str | None:
        """Enter scan mode: wait for the next card tap and return its UID.

        While in scan mode, detected cards are captured instead of dispatched.
        Returns the UID string, or None on timeout.
        """
        self._scanned_uid = None
        self._scan_event.clear()
        self._scan_waiting = True
        try:
            got_card = self._scan_event.wait(timeout=timeout)
        finally:
            self._scan_waiting = False
        if got_card and self._scanned_uid:
            uid = self._scanned_uid
            self._scanned_uid = None
            return uid
        self._scanned_uid = None
        return None

    def register_card(self, uid: str, action: str, label: str = "") -> None:
        """Add or update a card mapping and persist to config file."""
        with self._lock:
            for card in self._cards:
                if card["uid"] == uid:
                    card["action"] = action
                    card["label"] = label
                    self._save_config()
                    return
            self._cards.append({"uid": uid, "action": action, "label": label})
            self._save_config()

    def remove_card(self, uid: str) -> bool:
        """Remove a card mapping. Returns True if found and removed."""
        with self._lock:
            before = len(self._cards)
            self._cards = [c for c in self._cards if c["uid"] != uid]
            if len(self._cards) < before:
                self._save_config()
                return True
            return False

    def _load_config(self) -> None:
        """Load card mappings from the JSON config file."""
        try:
            with open(self._config_path, "r") as f:
                data = json.load(f)
            self._cards = data.get("cards", [])
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            self._cards = []

    def _save_config(self) -> None:
        """Persist card mappings to the JSON config file (caller holds _lock)."""
        try:
            with open(self._config_path, "w") as f:
                json.dump({"cards": self._cards}, f, indent=2)
        except OSError as e:
            print(f"[NFC Reader] WARNING: Could not save config: {e}")

    def _poll_loop(self) -> None:
        """Background thread: poll for NFC cards and dispatch actions."""
        from mfrc522 import SimpleMFRC522
        import RPi.GPIO as GPIO

        while self._running:
            try:
                reader = self._reader
                if reader is None:
                    break
                # read_id_no_block returns (id, _) or (None, None)
                uid_int = reader.read_id_no_block()
                if uid_int is not None:
                    # Convert integer UID to byte-based hex string
                    uid_hex = hex(uid_int).upper().replace("0X", "0x")
                    self._handle_card(uid_hex)
            except Exception as e:
                if self._running:
                    print(f"[NFC Reader] Poll error: {e}")
            time.sleep(POLL_INTERVAL)

    def _handle_card(self, uid: str) -> None:
        """Process a detected card UID with debounce."""
        now = time.monotonic()

        # Debounce: ignore same card within the window
        if uid == self._last_uid and (now - self._last_time) < DEBOUNCE_SECONDS:
            return

        self._last_uid = uid
        self._last_time = now

        # Record last scan
        from datetime import datetime
        scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            self._last_scan = {"uid": uid, "time": scan_time}

        # Scan-to-register mode: capture UID instead of dispatching
        if self._scan_waiting:
            self._scanned_uid = uid
            self._scan_event.set()
            self._beep_confirm()
            print(f"[NFC Reader] Scan captured: {uid}")
            return

        # Look up action
        action = None
        label = uid
        with self._lock:
            for card in self._cards:
                if card["uid"] == uid:
                    action = card.get("action")
                    label = card.get("label", uid)
                    break

        if action:
            print(f"[NFC Reader] Card '{label}' ({uid}) → {action}")
            self._dispatch(action, label)
        else:
            print(f"[NFC Reader] Unknown card: {uid}")
            self._beep_error()

    def _dispatch(self, action: str, label: str) -> None:
        """Execute the mapped action on the RoomGuard."""
        try:
            if action == "toggle_arm":
                armed = self._guard.toggle_arm()
                state = "Armed" if armed else "Disarmed"
                print(f"[NFC Reader] {state}")
            elif action == "toggle_led":
                with self._guard._lock:
                    current = self._guard._led_on
                self._guard.set_led(not current)
                self._beep_confirm()
            elif action.startswith("play_melody:"):
                melody_name = action.split(":", 1)[1]
                self._guard.play_melody_by_name(melody_name)
            elif action == "play_random":
                self._guard.play_current_melody()
            elif action == "stop_melody":
                self._guard.stop_melody()
                self._beep_confirm()
            elif action == "next_melody":
                name = self._guard.next_melody()
                print(f"[NFC Reader] Next: {name}")
            elif action == "prev_melody":
                name = self._guard.prev_melody()
                print(f"[NFC Reader] Prev: {name}")
            else:
                print(f"[NFC Reader] Unknown action: {action}")
                self._beep_error()
                return

            self._guard._log_message(f"NFC: {label} → {action}")
        except Exception as e:
            print(f"[NFC Reader] Action '{action}' failed: {e}")

    def _beep_confirm(self) -> None:
        """Short high-pitched confirmation beep."""
        try:
            from buzzer import NOTE_C5
            self._guard._buzzer.play_tone(NOTE_C5, 0.08)
        except Exception:
            pass

    def _beep_error(self) -> None:
        """Short low-pitched error beep."""
        try:
            from buzzer import NOTE_C4
            self._guard._buzzer.play_tone(NOTE_C4, 0.15)
        except Exception:
            pass
