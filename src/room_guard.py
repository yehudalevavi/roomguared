#!/usr/bin/env python3
"""
Room Guard — Motion detection alarm system for Raspberry Pi 4.

Provides a RoomGuard class that can be controlled programmatically
(by the Flask web app) or run standalone from the command line.
"""

import threading
import signal
import sys
import time
from datetime import datetime

from buzzer import Buzzer, MELODY_STARTUP, MELODY_DISARM, melody_duration
from melody_library import MOTION_MELODIES, get_random_melody
from lcd_display import LCDDisplay

# --- Configuration ---
PIR_PIN = 17     # GPIO 17 (Physical pin 11) — PIR sensor OUT
LED_PIN = 27     # GPIO 27 (Physical pin 13) — LED anode via 220Ω
COOLDOWN = 10    # Seconds to wait after alert before next detection
MAX_LOG_ENTRIES = 100
LCD_PAGE_INTERVAL = 5    # Seconds between LCD page cycles
LCD_FLASH_DURATION = 3   # Seconds to show event messages on LCD


class RoomGuard:
    """
    Controllable motion detection alarm.

    Provides arm/disarm, LED control, melody playback, and event logging.
    All methods are thread-safe for use with Flask.
    """

    def __init__(self, pir_pin=PIR_PIN, led_pin=LED_PIN, cooldown=COOLDOWN):
        self.pir_pin = pir_pin
        self.led_pin = led_pin
        self.cooldown = cooldown

        self._armed = False
        self._led_on = False
        self._playing = False
        self._lock = threading.Lock()
        self._event_log: list[dict] = []
        self._motion_count = 0
        self._last_event_time: str | None = None
        self._started_at: str | None = None

        # Hardware — initialized in start()
        self._pir = None
        self._led = None
        self._buzzer = Buzzer()
        self._lcd = LCDDisplay()

        # LCD cycling state
        self._lcd_running = False
        self._lcd_thread: threading.Thread | None = None
        self._lcd_flash_until: float = 0  # timestamp when flash message expires
        self._lcd_lock = threading.Lock()  # protects all LCD hardware writes

    def start(self) -> None:
        """Initialize hardware devices."""
        from gpiozero import MotionSensor, LED as GPIOLed
        self._pir = MotionSensor(self.pir_pin, queue_len=1, sample_rate=10, threshold=0.5)
        self._led = GPIOLed(self.led_pin)
        self._buzzer.start()
        self._started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Initialize LCD (non-fatal if it fails)
        try:
            self._lcd.start()
            self._lcd_running = True
            self._lcd_thread = threading.Thread(target=self._lcd_cycle_loop, daemon=True)
            self._lcd_thread.start()
        except Exception as e:
            print(f"[Room Guard] WARNING: LCD init failed: {e}")
            self._lcd_running = False

        self._log_message("System started")

    def stop(self) -> None:
        """Shut down hardware."""
        self.disarm()
        self._lcd_running = False
        if self._led:
            self._led.off()
        self._buzzer.play_melody(MELODY_DISARM)
        self._buzzer.stop()
        self._lcd_show("Room Guard OFF", "Goodbye!")
        time.sleep(1)
        self._lcd.stop()
        self._log_message("System stopped")

    def arm(self) -> None:
        """Enable motion detection."""
        with self._lock:
            if self._armed:
                return
            self._armed = True
            if self._pir:
                self._pir.when_motion = self._on_motion
        self._lcd_flash(">> ARMED <<", "Watching...")
        self._log_message("Armed — watching for motion")

    def disarm(self) -> None:
        """Disable motion detection."""
        with self._lock:
            if not self._armed:
                return
            self._armed = False
            if self._pir:
                self._pir.when_motion = None
        self._lcd_flash(">> DISARMED <<", "Sensor paused")
        self._log_message("Disarmed")

    def set_led(self, on: bool) -> None:
        """Manually control the LED."""
        with self._lock:
            self._led_on = on
            if self._led:
                if on:
                    self._led.on()
                else:
                    self._led.off()
        self._lcd_flash("LED", "ON" if on else "OFF")

    def play_melody_by_name(self, name: str) -> bool:
        """Play a specific melody by name. Returns False if not found or busy."""
        for mel_name, notes in MOTION_MELODIES:
            if mel_name == name:
                self._lcd_flash("Now playing:", name[:16])
                threading.Thread(
                    target=self._play_melody_thread,
                    args=(mel_name, notes),
                    daemon=True,
                ).start()
                return True
        return False

    def get_melody_names(self) -> list[str]:
        """Return all available melody names."""
        return [name for name, _ in MOTION_MELODIES]

    def get_status(self) -> dict:
        """Return current system state as a dict."""
        with self._lock:
            return {
                "armed": self._armed,
                "led_on": self._led_on,
                "playing": self._playing,
                "motion_count": self._motion_count,
                "last_event": self._last_event_time,
                "started_at": self._started_at,
                "cooldown": self.cooldown,
            }

    def get_logs(self, limit: int = 50) -> list[dict]:
        """Return recent log entries."""
        with self._lock:
            return list(reversed(self._event_log[-limit:]))

    # --- Internal ---

    def _on_motion(self, sensor=None) -> None:
        """PIR motion callback — runs in gpiozero's callback thread."""
        with self._lock:
            if not self._armed or self._playing:
                return
            self._playing = True

        name, melody = get_random_melody()
        self._log_message(f"MOTION DETECTED! Playing: {name}")
        with self._lock:
            self._motion_count += 1
            self._last_event_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self._lcd_flash("! MOTION !", name[:16])

        if self._led:
            self._led.on()
        self._buzzer.play_melody(melody)
        if self._led and not self._led_on:
            self._led.off()

        time.sleep(self.cooldown)
        with self._lock:
            self._playing = False
        self._log_message("Watching...")

    def _play_melody_thread(self, name: str, notes: list) -> None:
        """Play a melody in a background thread (for on-demand requests)."""
        with self._lock:
            if self._playing:
                return
            self._playing = True
        self._log_message(f"Playing on demand: {name}")
        self._buzzer.play_melody(notes)
        with self._lock:
            self._playing = False

    def _log_message(self, message: str) -> None:
        """Add a timestamped log entry."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {"time": timestamp, "message": message}
        print(f"[Room Guard] {timestamp} — {message}")
        with self._lock:
            self._event_log.append(entry)
            if len(self._event_log) > MAX_LOG_ENTRIES:
                self._event_log = self._event_log[-MAX_LOG_ENTRIES:]

    # --- LCD ---

    def _lcd_show(self, line1: str, line2: str = "") -> None:
        """Write text to the LCD (safe — does nothing if LCD unavailable)."""
        try:
            if self._lcd._lcd is not None:
                with self._lcd_lock:
                    self._lcd.write(line1, line2)
        except Exception:
            pass

    def _lcd_flash(self, line1: str, line2: str = "") -> None:
        """Show a temporary message on the LCD for LCD_FLASH_DURATION seconds."""
        self._lcd_flash_until = time.monotonic() + LCD_FLASH_DURATION
        try:
            if self._lcd._lcd is not None:
                with self._lcd_lock:
                    # Clear cached lines so the next cycle page does a full rewrite
                    self._lcd._line1 = ""
                    self._lcd._line2 = ""
                    self._lcd.write(line1, line2)
        except Exception:
            pass

    def _lcd_cycle_loop(self) -> None:
        """Background thread: cycle LCD between status pages."""
        page = 0
        while self._lcd_running:
            # If a flash message is active, don't overwrite it
            if time.monotonic() < self._lcd_flash_until:
                time.sleep(0.5)
                continue

            now = datetime.now()

            if page == 0:
                # Page 1: Status + current time
                with self._lock:
                    state = "ARMED" if self._armed else "DISARMED"
                    if self._playing:
                        state = "PLAYING"
                self._lcd_show(
                    f"Room Guard {state}"[:16],
                    now.strftime("%H:%M:%S %d/%m"),
                )
            elif page == 1:
                # Page 2: Motion stats
                with self._lock:
                    count = self._motion_count
                    last = self._last_event_time
                last_short = last.split(" ")[1] if last else "None"
                self._lcd_show(
                    f"Motion: {count}",
                    f"Last: {last_short}",
                )
            elif page == 2:
                # Page 3: LED status + uptime
                with self._lock:
                    led = "ON" if self._led_on else "OFF"
                self._lcd_show(
                    f"LED: {led}",
                    now.strftime("%Y-%m-%d"),
                )

            # Wait for page interval, checking for stop every 0.5s
            for _ in range(LCD_PAGE_INTERVAL * 2):
                if not self._lcd_running:
                    return
                if time.monotonic() < self._lcd_flash_until:
                    break
                time.sleep(0.5)

            page = (page + 1) % 3


# --- Standalone CLI mode ---

def main() -> None:
    """Run Room Guard in standalone mode (no web UI)."""
    try:
        guard = RoomGuard()
        guard.start()
    except Exception as e:
        print(f"[Room Guard] ERROR: {e}")
        print("[Room Guard] This script must run on a Raspberry Pi with gpiozero installed.")
        sys.exit(1)

    def shutdown(signum=None, frame=None):
        print()
        guard.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"[Room Guard] 20 melodies loaded, {COOLDOWN}s cooldown")
    guard._buzzer.play_melody(MELODY_STARTUP)

    guard._log_message("PIR sensor calibrating (40s)...")
    time.sleep(40)
    guard._log_message("PIR sensor ready!")

    guard.arm()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
