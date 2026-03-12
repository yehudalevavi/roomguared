#!/usr/bin/env python3
"""
Hardware test for the LCD1602 display (4-bit parallel mode).

Run this on the Raspberry Pi after wiring the LCD to validate
that the display is connected correctly and showing text.

Wiring (see DESIGN.md for full details):
    RS  → RPi Pin 37 (GPIO 26)
    E   → RPi Pin 35 (GPIO 19)
    D4  → RPi Pin 33 (GPIO 13)
    D5  → RPi Pin 31 (GPIO 6)
    D6  → RPi Pin 29 (GPIO 5)
    D7  → RPi Pin 23 (GPIO 11)
    VSS → GND, VDD → 5V, RW → GND
    V0  → Potentiometer wiper (contrast)
    A   → 5V via 220 ohm, K → GND (backlight)

Usage:
    python3 src/test_lcd.py
"""

import sys
import time

sys.path.insert(0, "src")

from lcd_display import LCDDisplay


def main() -> None:
    lcd = LCDDisplay()

    print("=== LCD1602 Display Test ===\n")
    print(f"Pins: RS=GPIO{lcd.rs}, E=GPIO{lcd.e}, "
          f"D4=GPIO{lcd.data_pins[0]}, D5=GPIO{lcd.data_pins[1]}, "
          f"D6=GPIO{lcd.data_pins[2]}, D7=GPIO{lcd.data_pins[3]}")
    print(f"Display size: {lcd.cols}x{lcd.rows}\n")

    try:
        lcd.start()
    except Exception as e:
        print(f"ERROR: Could not initialize LCD: {e}")
        print("Make sure you're running on a Raspberry Pi with RPLCD installed:")
        print("  pip3 install RPLCD")
        sys.exit(1)

    try:
        # Test 1: Hello message
        print("1) Writing 'Hello Room Guard!' on line 1, 'LCD Working!' on line 2...")
        lcd.write("Hello Room Guard", "LCD Working!")
        time.sleep(3)

        # Test 2: Clear and write new text
        print("2) Clearing display and writing new text...")
        lcd.clear()
        time.sleep(0.5)
        lcd.write("Test 2: Clear OK", "New text works!")
        time.sleep(3)

        # Test 3: Overwrite without clearing
        print("3) Overwriting text without clearing...")
        lcd.write("Line 1 Updated!", "Line 2 Updated!")
        time.sleep(3)

        # Test 4: Long text (should truncate to 16 chars)
        print("4) Testing text truncation (long text)...")
        lcd.write("This text is way too long for LCD", "Also way too long here!")
        time.sleep(3)

        # Test 5: Empty lines
        print("5) Clearing to blank...")
        lcd.write("", "")
        time.sleep(2)

        # Final message
        print("6) Displaying final message...")
        lcd.write("LCD Test: PASS", "All checks OK!")
        time.sleep(3)

    finally:
        lcd.stop()

    print(f"\n=== Test complete ===\n")
    print("If you saw text on the LCD at each step, the wiring is correct! \u2705")
    print("\nTroubleshooting:")
    print("  - No text visible?  Turn the potentiometer slowly until text appears.")
    print("  - Backlight off?    Check the 220\u03a9 resistor from LCD pin A to 5V rail.")
    print("  - Garbled text?     Double-check D4-D7 wires match the correct GPIO pins.")


if __name__ == "__main__":
    main()
