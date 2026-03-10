#!/usr/bin/env python3
"""
Passive buzzer module with PWM tone generation and predefined melodies.

Uses gpiozero's PWMOutputDevice to drive a passive buzzer at specific
frequencies. Unlike an active buzzer (fixed tone on/off), a passive
buzzer can play any audible frequency, enabling real melodies.

Wiring:
    Buzzer (+) → RPi Pin 15 (GPIO 22)
    Buzzer (−) → Breadboard − rail (GND)
"""

import time

BUZZER_PIN = 22  # GPIO 22 (Physical pin 15) — same pin as the old active buzzer

# Standard musical note frequencies (Hz)
NOTE_C4 = 261.63
NOTE_D4 = 293.66
NOTE_E4 = 329.63
NOTE_F4 = 349.23
NOTE_G4 = 392.00
NOTE_A4 = 440.00
NOTE_B4 = 493.88
NOTE_C5 = 523.25
NOTE_D5 = 587.33
NOTE_E5 = 659.25
NOTE_F5 = 698.46
NOTE_G5 = 783.99
NOTE_A5 = 880.00
NOTE_B5 = 987.77
NOTE_C6 = 1046.50
REST = 0  # silence

# Predefined melodies: list of (frequency_hz, duration_seconds) tuples
# REST (0 Hz) entries create silent gaps between notes.

MELODY_ALARM = [
    # Urgent two-tone siren pattern (like a European emergency siren)
    (NOTE_A5, 0.15), (NOTE_E5, 0.15),
    (NOTE_A5, 0.15), (NOTE_E5, 0.15),
    (NOTE_A5, 0.15), (NOTE_E5, 0.15),
    (REST, 0.10),
    (NOTE_A5, 0.15), (NOTE_E5, 0.15),
    (NOTE_A5, 0.15), (NOTE_E5, 0.15),
    (NOTE_A5, 0.15), (NOTE_E5, 0.15),
    (REST, 0.10),
    # Accelerating finish
    (NOTE_A5, 0.10), (NOTE_E5, 0.10),
    (NOTE_A5, 0.08), (NOTE_E5, 0.08),
    (NOTE_A5, 0.06), (NOTE_E5, 0.06),
    (NOTE_A5, 0.80),
]

MELODY_STARTUP = [
    # Friendly ascending jingle
    (NOTE_C5, 0.15), (REST, 0.05),
    (NOTE_E5, 0.15), (REST, 0.05),
    (NOTE_G5, 0.15), (REST, 0.05),
    (NOTE_C6, 0.30),
]

MELODY_ARM = [
    # Short confirmation double-beep
    (NOTE_E5, 0.10), (REST, 0.05),
    (NOTE_E5, 0.15),
]

MELODY_DISARM = [
    # Descending three-note sign-off
    (NOTE_G5, 0.15), (REST, 0.05),
    (NOTE_E5, 0.15), (REST, 0.05),
    (NOTE_C5, 0.30),
]

MELODY_SENSOR_ERROR = [
    # Low double-beep — something's wrong
    (NOTE_C4, 0.20), (REST, 0.10),
    (NOTE_C4, 0.20),
]


def melody_duration(melody: list[tuple[float, float]]) -> float:
    """Calculate the total duration of a melody in seconds."""
    return sum(duration for _, duration in melody)


class Buzzer:
    """
    Passive buzzer controller using PWM.

    Call start() before playing tones, and stop() when done.
    """

    def __init__(self, pin: int = BUZZER_PIN):
        self.pin = pin
        self._device = None

    def start(self) -> None:
        """Initialize the PWM output device."""
        from gpiozero import PWMOutputDevice
        self._device = PWMOutputDevice(self.pin, frequency=440)
        self._device.off()

    def stop(self) -> None:
        """Release the hardware."""
        if self._device is not None:
            self._device.off()
            self._device.close()
            self._device = None

    def play_tone(self, frequency: float, duration: float) -> None:
        """
        Play a single tone at the given frequency for the given duration.

        Args:
            frequency: Tone frequency in Hz. Use 0 for silence (rest).
            duration: How long to play in seconds.
        """
        if self._device is None:
            raise RuntimeError("Buzzer not started. Call start() first.")

        if frequency <= 0:
            self._device.off()
            time.sleep(duration)
            return

        self._device.frequency = frequency
        self._device.value = 0.5  # 50% duty cycle for max volume
        time.sleep(duration)
        self._device.off()

    def play_melody(self, melody: list[tuple[float, float]]) -> None:
        """
        Play a sequence of tones.

        Args:
            melody: List of (frequency_hz, duration_seconds) tuples.
                    Use frequency=0 (REST) for silent gaps.
        """
        if self._device is None:
            raise RuntimeError("Buzzer not started. Call start() first.")

        for frequency, duration in melody:
            self.play_tone(frequency, duration)

    @property
    def is_active(self) -> bool:
        """Return True if the buzzer is currently sounding."""
        if self._device is None:
            return False
        return self._device.value > 0
