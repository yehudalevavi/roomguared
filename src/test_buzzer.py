#!/usr/bin/env python3
"""
Hardware test for the passive buzzer.

Plays each predefined melody so you can verify the passive buzzer is
wired correctly and sounds distinct for each event type.

Wiring:
    Buzzer (+) → RPi Pin 15 (GPIO 22)
    Buzzer (−) → Breadboard − rail (GND)

Usage:
    python3 src/test_buzzer.py
"""

import sys
import time

sys.path.insert(0, "src")

from buzzer import (
    Buzzer,
    MELODY_STARTUP,
    MELODY_ARM,
    MELODY_ALARM,
    MELODY_DISARM,
    MELODY_SENSOR_ERROR,
    melody_duration,
)

MELODIES = [
    ("STARTUP", "Friendly ascending jingle (plays on boot)", MELODY_STARTUP),
    ("ARM", "Short confirmation beep (system starts watching)", MELODY_ARM),
    ("ALARM", "Urgent siren pattern (motion detected!)", MELODY_ALARM),
    ("SENSOR_ERROR", "Low double-beep (sensor read failed)", MELODY_SENSOR_ERROR),
    ("DISARM", "Descending sign-off (system shutting down)", MELODY_DISARM),
]


def main() -> None:
    buzzer = Buzzer()

    print("=== Passive Buzzer Test ===\n")
    print(f"Buzzer on GPIO {buzzer.pin} (Physical pin 15)")
    print(f"Playing {len(MELODIES)} melodies...\n")

    try:
        buzzer.start()
    except Exception as e:
        print(f"ERROR: Could not initialize buzzer: {e}")
        print("Make sure you're running on a Raspberry Pi.")
        sys.exit(1)

    try:
        for i, (name, description, melody) in enumerate(MELODIES, 1):
            duration = melody_duration(melody)
            print(f"  [{i}/{len(MELODIES)}] {name} — {description} ({duration:.1f}s)")
            buzzer.play_melody(melody)
            print(f"           Done.")

            if i < len(MELODIES):
                print(f"           (pause 1.5s)\n")
                time.sleep(1.5)

    finally:
        buzzer.stop()

    print(f"\n=== Test complete ===\n")
    print("If you heard 5 distinct melodies, the passive buzzer is working! ✅")
    print("If you heard clicking instead of tones, you may still have the active buzzer connected.")


if __name__ == "__main__":
    main()
