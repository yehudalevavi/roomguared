#!/usr/bin/env python3
"""
Hardware test for the passive buzzer.

Plays system melodies and a random sample from the 20-melody motion
library so you can verify the passive buzzer sounds correct.

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
    MELODY_DISARM,
    MELODY_SENSOR_ERROR,
    melody_duration,
)
from melody_library import MOTION_MELODIES, get_random_melody

SYSTEM_MELODIES = [
    ("STARTUP", "Friendly ascending jingle (plays on boot)", MELODY_STARTUP),
    ("ARM", "Short confirmation beep (system starts watching)", MELODY_ARM),
    ("SENSOR_ERROR", "Low double-beep (sensor read failed)", MELODY_SENSOR_ERROR),
    ("DISARM", "Descending sign-off (system shutting down)", MELODY_DISARM),
]


def main() -> None:
    buzzer = Buzzer()

    print("=== Passive Buzzer Test ===\n")
    print(f"Buzzer on GPIO {buzzer.pin} (Physical pin 15)")
    total = len(SYSTEM_MELODIES) + 3  # 4 system + 3 random motion samples
    print(f"Playing {len(SYSTEM_MELODIES)} system melodies + 3 random motion melodies...\n")

    try:
        buzzer.start()
    except Exception as e:
        print(f"ERROR: Could not initialize buzzer: {e}")
        print("Make sure you're running on a Raspberry Pi.")
        sys.exit(1)

    idx = 1
    try:
        # System melodies
        print("--- System Melodies ---\n")
        for name, description, melody in SYSTEM_MELODIES:
            duration = melody_duration(melody)
            print(f"  [{idx}/{total}] {name} — {description} ({duration:.1f}s)")
            buzzer.play_melody(melody)
            print(f"           Done.")
            print(f"           (pause 1.5s)\n")
            time.sleep(1.5)
            idx += 1

        # Random motion melodies
        print("--- Motion Melodies (3 random samples from library of 20) ---\n")
        for _ in range(3):
            name, melody = get_random_melody()
            duration = melody_duration(melody)
            print(f"  [{idx}/{total}] {name} ({duration:.1f}s)")
            buzzer.play_melody(melody)
            print(f"           Done.")
            if idx < total:
                print(f"           (pause 1.5s)\n")
                time.sleep(1.5)
            idx += 1

    finally:
        buzzer.stop()

    print(f"\n=== Test complete ===\n")
    print(f"Library contains {len(MOTION_MELODIES)} motion melodies.")
    print("If you heard tones (not clicks), the passive buzzer is working! ✅")


if __name__ == "__main__":
    main()
