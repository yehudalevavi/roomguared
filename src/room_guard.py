#!/usr/bin/env python3
"""
Room Guard — Motion detection alarm system for Raspberry Pi 4.

Detects motion using an HC-SR501 PIR sensor and responds by
lighting an LED and sounding a passive buzzer with distinct melodies.
"""

import signal
import sys
import time
from datetime import datetime

try:
    from gpiozero import MotionSensor, LED
except ImportError:
    print("[Room Guard] ERROR: gpiozero not found. This script must run on a Raspberry Pi.")
    print("[Room Guard] Install with: pip3 install gpiozero lgpio")
    sys.exit(1)

from buzzer import Buzzer, MELODY_STARTUP, MELODY_DISARM, melody_duration
from melody_library import get_random_melody

# --- Configuration ---
PIR_PIN = 17     # GPIO 17 (Physical pin 11) — PIR sensor OUT
LED_PIN = 27     # GPIO 27 (Physical pin 13) — LED anode via 220Ω
COOLDOWN = 10    # Seconds to wait after alert before next detection

# --- State ---
_running = True


def log(message: str) -> None:
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Room Guard] {timestamp} — {message}")


def shutdown(signum: int = None, frame=None) -> None:
    """Clean up and exit."""
    global _running
    _running = False
    print()
    log("Shutting down...")
    led.off()
    buzzer_dev.play_melody(MELODY_DISARM)
    buzzer_dev.stop()
    log("GPIO cleaned up. Goodbye!")
    sys.exit(0)


def motion_detected(sensor: MotionSensor) -> None:
    """Callback triggered when PIR sensor detects motion."""
    name, melody = get_random_melody()
    log(f"MOTION DETECTED! Playing: {name}")
    led.on()
    buzzer_dev.play_melody(melody)
    led.off()
    log(f"Cooldown {COOLDOWN}s...")
    time.sleep(COOLDOWN)
    log("Watching...")


# --- Devices (module-level so shutdown() can access them) ---
pir = MotionSensor(PIR_PIN, queue_len=1, sample_rate=10, threshold=0.5)
led = LED(LED_PIN)
buzzer_dev = Buzzer()


def main() -> None:
    """Initialize GPIO, register callbacks, and wait for motion."""
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    buzzer_dev.start()

    print("[Room Guard] Starting up...")
    print(f"[Room Guard] PIR sensor on GPIO {PIR_PIN}")
    print(f"[Room Guard] LED on GPIO {LED_PIN}")
    print(f"[Room Guard] Passive buzzer on GPIO {buzzer_dev.pin}")
    alarm_dur = melody_duration(MELODY_ALARM)
    print(f"[Room Guard] Alert: ~{alarm_dur:.1f}s melody, {COOLDOWN}s cooldown")
    print("[Room Guard] Waiting for motion...")
    print()

    # Startup jingle
    buzzer_dev.play_melody(MELODY_STARTUP)

    # PIR sensors need time to calibrate
    log("PIR sensor calibrating (40s)...")
    time.sleep(40)
    log("PIR sensor ready!")

    # Register motion callback
    pir.when_motion = motion_detected

    # Keep the main thread alive
    while _running:
        time.sleep(1)


if __name__ == "__main__":
    main()
