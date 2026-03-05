#!/usr/bin/env python3
"""
Hardware test for the DHT11 temperature and humidity sensor.

Run this on the Raspberry Pi after wiring the DHT11 to validate
that the sensor is connected correctly and returning data.

Wiring:
    VCC  → RPi Pin 2 (5V)
    DATA → RPi Pin 7 (GPIO 4)
    GND  → RPi Pin 9 (GND)

Usage:
    python3 src/test_dht11.py
"""

import sys
import time

# Allow running from project root
sys.path.insert(0, "src")

from dht11_sensor import DHT11Sensor

NUM_READINGS = 10
INTERVAL = 2  # seconds between readings


def main() -> None:
    sensor = DHT11Sensor()

    print("=== DHT11 Sensor Test ===\n")
    print(f"Reading GPIO pin {sensor.pin} (Physical pin 7)")
    print(f"Taking {NUM_READINGS} readings, one every {INTERVAL}s...\n")

    try:
        sensor.start()
    except Exception as e:
        print(f"ERROR: Could not initialize sensor: {e}")
        print("Make sure you're running on a Raspberry Pi with libgpiod2 installed:")
        print("  sudo apt install -y libgpiod2")
        sys.exit(1)

    successes = 0
    failures = 0

    try:
        for i in range(1, NUM_READINGS + 1):
            reading = sensor.read()

            if reading is not None:
                successes += 1
                print(f"  [{i:2d}/{NUM_READINGS}] ✅ Temp: {reading.temperature:.1f}°C  "
                      f"Humidity: {reading.humidity:.1f}%")
            else:
                failures += 1
                print(f"  [{i:2d}/{NUM_READINGS}] ❌ Read failed (all retries exhausted)")

            if i < NUM_READINGS:
                time.sleep(INTERVAL)

    finally:
        sensor.stop()

    # Summary
    print(f"\n=== Results: {successes}/{NUM_READINGS} successful reads ===\n")

    if successes >= 8:
        print("✅ Sensor is working great! Wiring looks correct.")
    elif successes >= 5:
        print("⚠️  Sensor is working but flaky. Check wiring and try again.")
    else:
        print("❌ Sensor is not working reliably. Check:")
        print("   - DATA wire is on Pin 7 (GPIO 4)")
        print("   - VCC wire is on Pin 2 (5V), not 3.3V")
        print("   - GND wire is on Pin 9 (GND)")
        sys.exit(1)


if __name__ == "__main__":
    main()
