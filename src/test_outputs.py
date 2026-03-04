#!/usr/bin/env python3
"""Quick test for LED and buzzer outputs — no sensor involved."""

import time
import sys

from gpiozero import LED, OutputDevice

LED_PIN = 27     # GPIO 27 (Physical pin 13)
BUZZER_PIN = 22  # GPIO 22 (Physical pin 15)

led = LED(LED_PIN)
buzzer = OutputDevice(BUZZER_PIN)

try:
    print("=== Output Test ===\n")

    print("1) LED on for 2 seconds...")
    led.on()
    time.sleep(2)
    led.off()
    print("   LED off.\n")

    print("2) Buzzer on for 1 second...")
    buzzer.on()
    time.sleep(1)
    buzzer.off()
    print("   Buzzer off.\n")

    print("3) Both on together for 2 seconds...")
    led.on()
    buzzer.on()
    time.sleep(2)
    led.off()
    buzzer.off()
    print("   Both off.\n")

    print("=== Test complete ===")
    print("If you saw the LED and heard the buzzer, your wiring is correct!")

finally:
    led.off()
    buzzer.off()
