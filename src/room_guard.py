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

from buzzer import Buzzer, MELODY_STARTUP, MELODY_ARM, MELODY_DISARM, NOTE_C4, NOTE_C5, melody_duration
from melody_library import MOTION_MELODIES, get_random_melody
from lcd_display import LCDDisplay
from bluetooth_speaker import BluetoothSpeaker
from spotify_player import SpotifyPlayer

# --- Configuration ---
PIR_PIN = 17     # GPIO 17 (Physical pin 11) — PIR sensor OUT
LED_PIN = 27     # GPIO 27 (Physical pin 13) — LED anode via 220Ω
COOLDOWN = 10    # Seconds to wait after alert before next detection
MAX_LOG_ENTRIES = 100
LCD_PAGE_INTERVAL = 10   # Seconds between LCD page cycles
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
        self._melody_index = 0

        # Hardware — initialized in start()
        self._pir = None
        self._led = None
        self._buzzer = Buzzer()
        self._lcd = LCDDisplay()

        # Media modules — initialized in start()
        self._bt_speaker = BluetoothSpeaker()
        self._spotify = SpotifyPlayer()

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

        # Start media modules (non-fatal if they fail)
        try:
            self._bt_speaker.start()
        except Exception as e:
            print(f"[Room Guard] WARNING: Bluetooth init failed: {e}")

        try:
            self._spotify.start()
        except Exception as e:
            print(f"[Room Guard] WARNING: Spotify init failed: {e}")

        # Auto-connect to previously paired BT speaker
        try:
            self._bt_speaker.auto_connect()
        except Exception as e:
            print(f"[Room Guard] BT auto-connect skipped: {e}")

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

        # Stop media modules
        try:
            self._spotify.stop()
        except Exception:
            pass
        try:
            self._bt_speaker.stop()
        except Exception:
            pass

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
                self._lcd_flash("Now playing:", name)
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

    def next_melody(self) -> str:
        """Select the next melody in the library (wraps around). Returns the name."""
        with self._lock:
            self._melody_index = (self._melody_index + 1) % len(MOTION_MELODIES)
            name = MOTION_MELODIES[self._melody_index][0]
            playing = self._playing
        self._lcd_flash(">>", name)
        if not playing:
            try:
                self._buzzer.play_tone(NOTE_C5, 0.05)
            except RuntimeError:
                pass
        self._log_message(f"Selected: {name}")
        return name

    def prev_melody(self) -> str:
        """Select the previous melody in the library (wraps around). Returns the name."""
        with self._lock:
            self._melody_index = (self._melody_index - 1) % len(MOTION_MELODIES)
            name = MOTION_MELODIES[self._melody_index][0]
            playing = self._playing
        self._lcd_flash("<<", name)
        if not playing:
            try:
                self._buzzer.play_tone(NOTE_C4, 0.05)
            except RuntimeError:
                pass
        self._log_message(f"Selected: {name}")
        return name

    def get_current_melody(self) -> tuple[int, str]:
        """Return the current melody (index, name)."""
        with self._lock:
            return self._melody_index, MOTION_MELODIES[self._melody_index][0]

    def play_current_melody(self) -> str:
        """Play the currently selected melody. Returns the melody name."""
        with self._lock:
            name, notes = MOTION_MELODIES[self._melody_index]
        self._lcd_flash("Playing:", name)
        threading.Thread(
            target=self._play_melody_thread,
            args=(name, notes),
            daemon=True,
        ).start()
        return name

    def stop_melody(self) -> None:
        """Stop the currently playing melody."""
        self._buzzer.cancel()
        with self._lock:
            self._playing = False
        self._log_message("Playback stopped")

    def toggle_arm(self) -> bool:
        """Toggle arm/disarm with sound cue. Returns the new armed state."""
        with self._lock:
            was_armed = self._armed
            playing = self._playing
        if playing:
            self.stop_melody()
            time.sleep(0.1)
        if was_armed:
            self.disarm()
            try:
                self._buzzer.play_melody(MELODY_DISARM)
            except RuntimeError:
                pass  # buzzer not available
            return False
        else:
            try:
                self._buzzer.play_melody(MELODY_ARM)
            except RuntimeError:
                pass  # buzzer not available
            self.arm()
            return True

    def get_status(self) -> dict:
        """Return current system state as a dict."""
        with self._lock:
            status = {
                "armed": self._armed,
                "led_on": self._led_on,
                "playing": self._playing,
                "motion_count": self._motion_count,
                "last_event": self._last_event_time,
                "started_at": self._started_at,
                "cooldown": self.cooldown,
                "current_melody": MOTION_MELODIES[self._melody_index][0],
                "current_melody_index": self._melody_index,
            }
        # Media status (outside main lock to avoid deadlock)
        try:
            status["bt_connected"] = self._bt_speaker.get_status().get("connected", False)
        except Exception:
            status["bt_connected"] = False
        try:
            status["spotify_authenticated"] = self._spotify.is_authenticated()
        except Exception:
            status["spotify_authenticated"] = False
        return status

    def get_logs(self, limit: int = 50) -> list[dict]:
        """Return recent log entries."""
        with self._lock:
            return list(reversed(self._event_log[-limit:]))

    # --- Media (Bluetooth + Spotify) ---

    def get_bt_status(self) -> dict:
        """Return Bluetooth speaker connection status."""
        return self._bt_speaker.get_status()

    def get_spotify_status(self) -> dict:
        """Return Spotify auth + playback status."""
        status = {
            "authenticated": self._spotify.is_authenticated(),
            "configured": self._spotify.is_configured(),
        }
        if status["authenticated"]:
            try:
                playback = self._spotify.get_current_playback()
                status["playback"] = playback
            except Exception:
                status["playback"] = None
            # Include active device info
            try:
                devices = self._spotify.list_devices()
                active = [d for d in devices if d.get("is_active")]
                status["active_device"] = active[0]["name"] if active else None
            except Exception:
                status["active_device"] = None
        return status

    def play_random_song(self) -> dict | None:
        """Play a random song from Spotify liked songs. Returns track info or None."""
        if not self._spotify.is_authenticated():
            self._log_message("Spotify not authenticated")
            return None
        try:
            track = self._spotify.play_random_liked_song()
            if track:
                self._lcd_flash("Spotify:", track["name"][:16])
                self._log_message(f"Spotify: {track['name']} — {track['artist']}")
            return track
        except Exception as e:
            self._log_message(f"Spotify play failed: {e}")
            return None

    def spotify_pause(self) -> bool:
        """Pause Spotify playback."""
        try:
            result = self._spotify.pause()
            if result:
                self._lcd_flash("Spotify", "Paused")
            return result
        except Exception as e:
            self._log_message(f"Spotify pause failed: {e}")
            return False

    def spotify_resume(self) -> bool:
        """Resume Spotify playback."""
        try:
            result = self._spotify.resume()
            if result:
                self._lcd_flash("Spotify", "Playing")
            return result
        except Exception as e:
            self._log_message(f"Spotify resume failed: {e}")
            return False

    def spotify_next(self) -> bool:
        """Skip to next Spotify track."""
        try:
            result = self._spotify.next_track()
            if result:
                self._lcd_flash("Spotify", ">> Next")
            return result
        except Exception as e:
            self._log_message(f"Spotify next failed: {e}")
            return False

    def spotify_prev(self) -> bool:
        """Skip to previous Spotify track."""
        try:
            result = self._spotify.prev_track()
            if result:
                self._lcd_flash("Spotify", "<< Prev")
            return result
        except Exception as e:
            self._log_message(f"Spotify prev failed: {e}")
            return False

    def spotify_volume(self, percent: int) -> bool:
        """Set Spotify playback volume (0-100)."""
        try:
            return self._spotify.set_volume(percent)
        except Exception as e:
            self._log_message(f"Spotify volume failed: {e}")
            return False

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

        self._lcd_flash("! MOTION !", name)

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

    def show_custom_message(self, line1: str, line2: str = "", duration: int = 10) -> None:
        """Show a user-supplied message on the LCD for *duration* seconds,
        then automatically return to the normal status cycle."""
        self._lcd_flash_until = time.monotonic() + duration
        try:
            if self._lcd._lcd is not None:
                with self._lcd_lock:
                    self._lcd._line1 = ""
                    self._lcd._line2 = ""
                    self._lcd.write(line1, line2)
        except Exception:
            pass
        self._log_message(f"LCD message: {line1}" + (f" / {line2}" if line2 else ""))

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
        """Background thread: cycle LCD between status pages with scrolling."""
        page = 0
        SCROLL_STEP_DELAY = 0.4   # seconds between scroll steps
        SCROLL_PAUSE_STEPS = 4    # steps to pause at each end before reversing
        TICKS_PER_PAGE = LCD_PAGE_INTERVAL * 2  # how many 0.5s ticks per page

        while self._lcd_running:
            if time.monotonic() < self._lcd_flash_until:
                time.sleep(0.5)
                continue

            # Build page content (line1 can be long, line2 is live clock)
            line1 = self._lcd_page_line1(page)
            max_offset = max(0, len(line1) - 16)
            offset = 0
            direction = 1  # 1 = scrolling right (offset increasing), -1 = left
            pause_counter = SCROLL_PAUSE_STEPS  # pause at start

            page_start = time.monotonic()
            while self._lcd_running and (time.monotonic() - page_start) < LCD_PAGE_INTERVAL:
                if time.monotonic() < self._lcd_flash_until:
                    break

                # Refresh line1 content (status may change)
                line1 = self._lcd_page_line1(page)
                max_offset = max(0, len(line1) - 16)

                # Live clock on line 2
                line2 = self._lcd_page_line2(page)

                try:
                    if self._lcd._lcd is not None:
                        with self._lcd_lock:
                            self._lcd.write_at_offset(line1, 0, offset)
                            self._lcd.write(line2=line2)
                except Exception:
                    pass

                time.sleep(SCROLL_STEP_DELAY)

                # Advance scroll position (bounce between ends)
                if max_offset > 0:
                    if pause_counter > 0:
                        pause_counter -= 1
                    else:
                        offset += direction
                        if offset >= max_offset:
                            offset = max_offset
                            direction = -1
                            pause_counter = SCROLL_PAUSE_STEPS
                        elif offset <= 0:
                            offset = 0
                            direction = 1
                            pause_counter = SCROLL_PAUSE_STEPS

            page = (page + 1) % 4

    def _lcd_page_line1(self, page: int) -> str:
        """Return the top-line text for the given page."""
        if page == 0:
            with self._lock:
                state = "ARMED" if self._armed else "DISARMED"
                if self._playing:
                    state = "PLAYING"
            return f"Room Guard {state}"
        elif page == 1:
            with self._lock:
                count = self._motion_count
            return f"Motion count: {count}"
        elif page == 2:
            with self._lock:
                led = "ON" if self._led_on else "OFF"
            return f"LED: {led}"
        elif page == 3:
            # Now Playing page — show current Spotify track or skip
            try:
                if self._spotify.is_authenticated():
                    playback = self._spotify.get_current_playback()
                    if playback and playback.get("is_playing"):
                        track = playback["track"]
                        return f"{track['name']} - {track['artist']}"
            except Exception:
                pass
            return "No music playing"
        return ""

    def _lcd_page_line2(self, page: int) -> str:
        """Return the bottom-line text for the given page (live clock)."""
        now = datetime.now()
        if page == 0:
            return now.strftime("%H:%M:%S %d/%m/%y")
        elif page == 1:
            with self._lock:
                last = self._last_event_time
            last_short = last.split(" ")[1] if last else "None"
            return f"Last: {last_short}"
        elif page == 2:
            return now.strftime("%H:%M:%S %d/%m/%y")
        elif page == 3:
            try:
                bt = self._bt_speaker.get_status()
                if bt.get("connected"):
                    return f"BT: {bt['device_name'][:12]}"
            except Exception:
                pass
            return now.strftime("%H:%M:%S %d/%m/%y")
        return ""


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

    # Start IR remote (non-fatal if unavailable)
    ir = None
    try:
        from ir_remote import IRRemote
        ir = IRRemote(guard)
        ir.start()
        print("[Room Guard] IR remote control active")
    except Exception as e:
        print(f"[Room Guard] IR remote not available: {e}")

    # Start NFC reader (non-fatal if unavailable)
    nfc = None
    try:
        from nfc_reader import NFCReader
        nfc = NFCReader(guard)
        nfc.start()
        print("[Room Guard] NFC card reader active")
    except Exception as e:
        print(f"[Room Guard] NFC reader not available: {e}")

    def shutdown(signum=None, frame=None):
        print()
        if nfc:
            nfc.stop()
        if ir:
            ir.stop()
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
