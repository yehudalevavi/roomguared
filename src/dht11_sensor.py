#!/usr/bin/env python3
"""
DHT11 temperature and humidity sensor module.

Provides a clean interface to read the DHT11 sensor, with retry logic
to handle the sensor's occasional read failures.

Wiring (Elegoo kit DHT11 module):
    VCC  → RPi Pin 2 (5V)
    DATA → RPi Pin 7 (GPIO 4)
    GND  → RPi Pin 9 (GND)
"""

import time

DHT11_PIN = 4  # GPIO 4 (Physical pin 7) — DHT11 data pin

# Valid ranges for the DHT11 sensor
TEMP_MIN = -10.0
TEMP_MAX = 60.0
HUMIDITY_MIN = 0.0
HUMIDITY_MAX = 100.0


class DHT11Reading:
    """A single temperature/humidity reading."""

    def __init__(self, temperature: float, humidity: float):
        self.temperature = temperature
        self.humidity = humidity

    def __repr__(self) -> str:
        return f"DHT11Reading(temperature={self.temperature}°C, humidity={self.humidity}%)"


class DHT11Sensor:
    """
    Wrapper around the DHT11 sensor with retry logic.

    The DHT11 uses a single-wire protocol that occasionally fails.
    This class retries reads and validates values are in range.
    """

    def __init__(self, pin: int = DHT11_PIN, max_retries: int = 5):
        self.pin = pin
        self.max_retries = max_retries
        self._device = None
        self._last_reading: DHT11Reading | None = None

    def start(self) -> None:
        """Initialize the sensor hardware."""
        import adafruit_dht
        import board

        board_pin = getattr(board, f"D{self.pin}")
        self._device = adafruit_dht.DHT11(board_pin, use_pulseio=False)

    def stop(self) -> None:
        """Release the sensor hardware."""
        if self._device is not None:
            self._device.exit()
            self._device = None

    def read(self) -> DHT11Reading | None:
        """
        Read temperature and humidity from the sensor.

        Retries up to max_retries times on failure. Returns None if all
        retries are exhausted. On success, caches the reading as the
        last known good value.
        """
        if self._device is None:
            raise RuntimeError("Sensor not started. Call start() first.")

        for attempt in range(self.max_retries):
            try:
                temperature = self._device.temperature
                humidity = self._device.humidity

                if temperature is None or humidity is None:
                    continue

                if not (TEMP_MIN <= temperature <= TEMP_MAX):
                    continue
                if not (HUMIDITY_MIN <= humidity <= HUMIDITY_MAX):
                    continue

                reading = DHT11Reading(temperature=temperature, humidity=humidity)
                self._last_reading = reading
                return reading

            except RuntimeError:
                # DHT11 frequently throws RuntimeError on read — this is normal
                time.sleep(0.5)

        return None

    @property
    def last_reading(self) -> DHT11Reading | None:
        """Return the last successful reading, or None if no reading yet."""
        return self._last_reading
