#!/usr/bin/env python3
"""
Room Guard — Motion detection alarm system for Raspberry Pi 4.

Detects motion using an HC-SR501 PIR sensor and responds by
lighting an LED and sounding an active buzzer.
"""

import signal
import sys
import time
from datetime import datetime

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("[Room Guard] ERROR: RPi.GPIO not found. This script must run on a Raspberry Pi.")
    print("[Room Guard] Install with: pip3 install RPi.GPIO")
    sys.exit(1)

# --- Configuration ---
PIR_PIN = 17     # GPIO 17 (Physical pin 11) — PIR sensor OUT
LED_PIN = 27     # GPIO 27 (Physical pin 13) — LED anode via 220Ω
BUZZER_PIN = 22  # GPIO 22 (Physical pin 15) — Active buzzer (+)
COOLDOWN = 5     # Seconds to keep LED/buzzer on after detection

# --- State ---
_running = True


def log(message: str) -> None:
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Room Guard] {timestamp} — {message}")


def alert_on() -> None:
    """Turn on LED and buzzer."""
    GPIO.output(LED_PIN, GPIO.HIGH)
    GPIO.output(BUZZER_PIN, GPIO.HIGH)


def alert_off() -> None:
    """Turn off LED and buzzer."""
    GPIO.output(LED_PIN, GPIO.LOW)
    GPIO.output(BUZZER_PIN, GPIO.LOW)


def motion_detected(channel: int) -> None:
    """Callback triggered when PIR sensor detects motion."""
    log("MOTION DETECTED!")
    alert_on()
    time.sleep(COOLDOWN)
    alert_off()
    log(f"Alert off after {COOLDOWN}s cooldown. Watching...")


def shutdown(signum: int = None, frame=None) -> None:
    """Clean up GPIO and exit."""
    global _running
    _running = False
    print()
    log("Shutting down...")
    alert_off()
    GPIO.cleanup()
    log("GPIO cleaned up. Goodbye!")
    sys.exit(0)


def main() -> None:
    """Initialize GPIO, register callbacks, and wait for motion."""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # GPIO setup
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(PIR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)

    print("[Room Guard] Starting up...")
    print(f"[Room Guard] PIR sensor on GPIO {PIR_PIN}")
    print(f"[Room Guard] LED on GPIO {LED_PIN}")
    print(f"[Room Guard] Buzzer on GPIO {BUZZER_PIN}")
    print(f"[Room Guard] Cooldown: {COOLDOWN}s")
    print("[Room Guard] Waiting for motion...")
    print()

    # PIR sensors need time to calibrate
    log("PIR sensor calibrating (30s)...")
    time.sleep(30)
    log("PIR sensor ready!")

    # Register edge detection callback
    GPIO.add_event_detect(
        PIR_PIN,
        GPIO.RISING,
        callback=motion_detected,
        bouncetime=COOLDOWN * 1000,
    )

    # Keep the main thread alive
    while _running:
        time.sleep(1)


if __name__ == "__main__":
    main()
