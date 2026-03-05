#!/usr/bin/env python3
"""
Unit tests for the DHT11 sensor module.

These tests mock the hardware so they can run anywhere (no Raspberry Pi needed).
Run with: python3 -m pytest tests/test_dht11_unit.py -v
"""

import sys
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# Mock hardware libraries before importing our module
sys.modules["adafruit_dht"] = MagicMock()
sys.modules["board"] = MagicMock()

sys.path.insert(0, "src")
from dht11_sensor import DHT11Sensor, DHT11Reading, TEMP_MIN, TEMP_MAX, HUMIDITY_MIN, HUMIDITY_MAX


class TestDHT11Reading(unittest.TestCase):
    """Tests for the DHT11Reading data class."""

    def test_reading_stores_values(self):
        reading = DHT11Reading(temperature=23.0, humidity=45.0)
        self.assertEqual(reading.temperature, 23.0)
        self.assertEqual(reading.humidity, 45.0)

    def test_reading_repr(self):
        reading = DHT11Reading(temperature=23.0, humidity=45.0)
        self.assertIn("23.0", repr(reading))
        self.assertIn("45.0", repr(reading))


class TestDHT11SensorInit(unittest.TestCase):
    """Tests for sensor initialization and configuration."""

    def test_default_pin(self):
        sensor = DHT11Sensor()
        self.assertEqual(sensor.pin, 4)

    def test_custom_pin(self):
        sensor = DHT11Sensor(pin=18)
        self.assertEqual(sensor.pin, 18)

    def test_default_max_retries(self):
        sensor = DHT11Sensor()
        self.assertEqual(sensor.max_retries, 5)

    def test_custom_max_retries(self):
        sensor = DHT11Sensor(max_retries=3)
        self.assertEqual(sensor.max_retries, 3)

    def test_last_reading_initially_none(self):
        sensor = DHT11Sensor()
        self.assertIsNone(sensor.last_reading)


class TestDHT11SensorRead(unittest.TestCase):
    """Tests for sensor read logic."""

    def setUp(self):
        self.sensor = DHT11Sensor()
        # Create a mock device
        self.mock_device = MagicMock()
        self.sensor._device = self.mock_device

    def test_read_without_start_raises(self):
        sensor = DHT11Sensor()
        with self.assertRaises(RuntimeError):
            sensor.read()

    def test_successful_read(self):
        self.mock_device.temperature = 23.0
        self.mock_device.humidity = 45.0

        reading = self.sensor.read()

        self.assertIsNotNone(reading)
        self.assertEqual(reading.temperature, 23.0)
        self.assertEqual(reading.humidity, 45.0)

    def test_successful_read_caches_last_reading(self):
        self.mock_device.temperature = 23.0
        self.mock_device.humidity = 45.0

        self.sensor.read()

        self.assertIsNotNone(self.sensor.last_reading)
        self.assertEqual(self.sensor.last_reading.temperature, 23.0)

    def test_none_temperature_retries(self):
        # First call returns None temp, second succeeds
        type(self.mock_device).temperature = PropertyMock(
            side_effect=[None, 23.0, 23.0, 23.0, 23.0]
        )
        type(self.mock_device).humidity = PropertyMock(
            side_effect=[50.0, 50.0, 50.0, 50.0, 50.0]
        )

        reading = self.sensor.read()

        self.assertIsNotNone(reading)
        self.assertEqual(reading.temperature, 23.0)

    def test_none_humidity_retries(self):
        type(self.mock_device).temperature = PropertyMock(
            side_effect=[23.0, 23.0, 23.0, 23.0, 23.0]
        )
        type(self.mock_device).humidity = PropertyMock(
            side_effect=[None, 50.0, 50.0, 50.0, 50.0]
        )

        reading = self.sensor.read()

        self.assertIsNotNone(reading)
        self.assertEqual(reading.humidity, 50.0)

    def test_runtime_error_retries(self):
        # Attempt 1: temp raises → caught. Attempt 2: temp ok, hum raises → caught.
        # Attempt 3: both succeed.
        type(self.mock_device).temperature = PropertyMock(
            side_effect=[RuntimeError("read failed"), 23.0, 23.0]
        )
        type(self.mock_device).humidity = PropertyMock(
            side_effect=[RuntimeError("read failed"), 50.0]
        )

        reading = self.sensor.read()

        self.assertIsNotNone(reading)

    def test_all_retries_exhausted_returns_none(self):
        self.sensor.max_retries = 3
        type(self.mock_device).temperature = PropertyMock(
            side_effect=RuntimeError("read failed")
        )

        reading = self.sensor.read()

        self.assertIsNone(reading)

    def test_temperature_out_of_range_high_retries(self):
        type(self.mock_device).temperature = PropertyMock(
            side_effect=[TEMP_MAX + 10, 23.0]
        )
        type(self.mock_device).humidity = PropertyMock(return_value=50.0)

        reading = self.sensor.read()

        self.assertIsNotNone(reading)
        self.assertEqual(reading.temperature, 23.0)

    def test_temperature_out_of_range_low_retries(self):
        type(self.mock_device).temperature = PropertyMock(
            side_effect=[TEMP_MIN - 10, 23.0]
        )
        type(self.mock_device).humidity = PropertyMock(return_value=50.0)

        reading = self.sensor.read()

        self.assertIsNotNone(reading)
        self.assertEqual(reading.temperature, 23.0)

    def test_humidity_out_of_range_retries(self):
        type(self.mock_device).temperature = PropertyMock(return_value=23.0)
        type(self.mock_device).humidity = PropertyMock(
            side_effect=[HUMIDITY_MAX + 10, 50.0]
        )

        reading = self.sensor.read()

        self.assertIsNotNone(reading)
        self.assertEqual(reading.humidity, 50.0)

    def test_boundary_values_accepted(self):
        """Values exactly at min/max boundaries should be accepted."""
        self.mock_device.temperature = TEMP_MIN
        self.mock_device.humidity = HUMIDITY_MIN

        reading = self.sensor.read()
        self.assertIsNotNone(reading)

        self.mock_device.temperature = TEMP_MAX
        self.mock_device.humidity = HUMIDITY_MAX

        reading = self.sensor.read()
        self.assertIsNotNone(reading)


class TestDHT11SensorLifecycle(unittest.TestCase):
    """Tests for start/stop lifecycle."""

    def test_start_creates_device(self):
        sensor = DHT11Sensor(pin=4)

        with patch.dict("sys.modules", {"adafruit_dht": MagicMock(), "board": MagicMock()}) as mods:
            mock_board = sys.modules["board"]
            mock_dht = sys.modules["adafruit_dht"]
            mock_board.D4 = "pin4"

            sensor.start()

            mock_dht.DHT11.assert_called_once_with("pin4", use_pulseio=False)

    def test_stop_calls_exit(self):
        sensor = DHT11Sensor()
        mock_device = MagicMock()
        sensor._device = mock_device

        sensor.stop()

        mock_device.exit.assert_called_once()
        self.assertIsNone(sensor._device)

    def test_stop_when_not_started(self):
        sensor = DHT11Sensor()
        sensor.stop()  # should not raise


if __name__ == "__main__":
    unittest.main()
