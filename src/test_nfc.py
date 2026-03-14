#!/usr/bin/env python3
"""
NFC reader hardware test — scan cards and print their UIDs.

Run on the Raspberry Pi to verify MFRC522 wiring and discover card UIDs
for registration. Press Ctrl+C to stop.

Usage:
    source .venv/bin/activate
    python3 src/test_nfc.py

Wiring (MFRC522 → RPi SPI0):
    SDA  → RPi Pin 24 (GPIO 8, CE0)
    SCK  → RPi Pin 23 (GPIO 11)
    MOSI → RPi Pin 19 (GPIO 10)
    MISO → RPi Pin 21 (GPIO 9)
    RST  → RPi Pin 22 (GPIO 25)
    VCC  → 3.3V (NOT 5V!)
    GND  → Breadboard − rail
"""

import time
import signal
import sys


def main():
    print("=" * 50)
    print("  NFC Reader Hardware Test (MFRC522)")
    print("=" * 50)
    print()

    # Verify SPI is enabled
    import os
    if not os.path.exists("/dev/spidev0.0"):
        print("ERROR: SPI not enabled!")
        print("  Run: sudo raspi-config nonint do_spi 0")
        print("  Then reboot the Pi.")
        sys.exit(1)

    print("SPI device found: /dev/spidev0.0 ✓")

    from mfrc522 import SimpleMFRC522
    import RPi.GPIO as GPIO

    reader = SimpleMFRC522()
    print("MFRC522 initialized ✓")
    print()
    print("Hold an NFC card/fob near the reader...")
    print("Press Ctrl+C to stop.")
    print("-" * 50)
    print()

    scan_count = 0
    last_uid = None
    last_time = 0

    def cleanup(signum=None, frame=None):
        print()
        print("-" * 50)
        print(f"Total scans: {scan_count}")
        GPIO.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    while True:
        try:
            uid_int = reader.read_id_no_block()
            if uid_int is not None:
                uid_hex = hex(uid_int).upper().replace("0X", "0x")
                now = time.monotonic()

                # Debounce display (1 second)
                if uid_hex != last_uid or (now - last_time) > 1.0:
                    scan_count += 1
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"  [{timestamp}] Card #{scan_count}: UID = {uid_hex}")
                    print(f"             Raw int: {uid_int}")
                    print()
                    last_uid = uid_hex
                    last_time = now

        except Exception as e:
            print(f"  Read error: {e}")

        time.sleep(0.3)


if __name__ == "__main__":
    main()
