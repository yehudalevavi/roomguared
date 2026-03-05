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
    from gpiozero import MotionSensor, LED, OutputDevice
except ImportError:
    print("[Room Guard] ERROR: gpiozero not found. This script must run on a Raspberry Pi.")
    print("[Room Guard] Install with: pip3 install gpiozero lgpio")
    sys.exit(1)

# --- Configuration ---
PIR_PIN = 17     # GPIO 17 (Physical pin 11) — PIR sensor OUT
LED_PIN = 27     # GPIO 27 (Physical pin 13) — LED anode via 220Ω
BUZZER_PIN = 22  # GPIO 22 (Physical pin 15) — Active buzzer (+)
COOLDOWN = 10    # Seconds to wait after alert before next detection

# Rhythmic alert melody (~5 seconds total)
# Each tuple: (buzzer_on_seconds, pause_seconds)
MELODY = [
    # Quick triple tap
    (0.12, 0.08),
    (0.12, 0.08),
    (0.12, 0.30),
    # Double tap
    (0.20, 0.12),
    (0.20, 0.50),
    # Quick triple tap
    (0.12, 0.08),
    (0.12, 0.08),
    (0.12, 0.30),
    # Double tap
    (0.20, 0.12),
    (0.20, 0.50),
    # Finale: accelerando into long beep
    (0.08, 0.05),
    (0.08, 0.05),
    (0.08, 0.05),
    (0.08, 0.05),
    (0.80, 0.00),
]

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
    buzzer.off()
    log("GPIO cleaned up. Goodbye!")
    sys.exit(0)


def motion_detected(sensor: MotionSensor) -> None:
    """Callback triggered when PIR sensor detects motion."""
    log("MOTION DETECTED!")
    for on_time, off_time in MELODY:
        led.on()
        buzzer.on()
        time.sleep(on_time)
        led.off()
        buzzer.off()
        if off_time > 0:
            time.sleep(off_time)
    log(f"Cooldown {COOLDOWN}s...")
    time.sleep(COOLDOWN)
    log("Watching...")


# --- Devices (module-level so shutdown() can access them) ---
pir = MotionSensor(PIR_PIN, queue_len=1, sample_rate=10, threshold=0.5)
led = LED(LED_PIN)
buzzer = OutputDevice(BUZZER_PIN)


def main() -> None:
    """Initialize GPIO, register callbacks, and wait for motion."""
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("[Room Guard] Starting up...")
    print(f"[Room Guard] PIR sensor on GPIO {PIR_PIN}")
    print(f"[Room Guard] LED on GPIO {LED_PIN}")
    print(f"[Room Guard] Buzzer on GPIO {BUZZER_PIN}")
    print(f"[Room Guard] Alert: ~5s melody, {COOLDOWN}s cooldown")
    print("[Room Guard] Waiting for motion...")
    print()

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
