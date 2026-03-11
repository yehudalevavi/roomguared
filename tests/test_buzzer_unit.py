#!/usr/bin/env python3
"""
Unit tests for the passive buzzer module.

These tests mock the hardware so they can run anywhere (no Raspberry Pi needed).
Run with: python3 -m pytest tests/test_buzzer_unit.py -v
"""

import sys
import time
import unittest
from unittest.mock import MagicMock, patch, call

# Mock gpiozero before importing our module
mock_gpiozero = MagicMock()
sys.modules["gpiozero"] = mock_gpiozero

sys.path.insert(0, "src")
from buzzer import (
    Buzzer,
    BUZZER_PIN,
    REST,
    NOTE_A4,
    NOTE_C5,
    NOTE_E5,
    MELODY_STARTUP,
    MELODY_ARM,
    MELODY_DISARM,
    MELODY_SENSOR_ERROR,
    melody_duration,
)
from melody_library import MOTION_MELODIES, get_random_melody


class TestBuzzerInit(unittest.TestCase):
    """Tests for buzzer initialization."""

    def test_default_pin(self):
        buzzer = Buzzer()
        self.assertEqual(buzzer.pin, BUZZER_PIN)

    def test_custom_pin(self):
        buzzer = Buzzer(pin=18)
        self.assertEqual(buzzer.pin, 18)

    def test_not_active_before_start(self):
        buzzer = Buzzer()
        self.assertFalse(buzzer.is_active)


class TestBuzzerLifecycle(unittest.TestCase):
    """Tests for start/stop lifecycle."""

    def test_start_creates_pwm_device(self):
        buzzer = Buzzer(pin=22)
        mock_pwm_cls = MagicMock()
        mock_gpiozero.PWMOutputDevice = mock_pwm_cls

        buzzer.start()

        mock_pwm_cls.assert_called_once_with(22, frequency=440)

    def test_start_turns_off_device(self):
        buzzer = Buzzer()
        mock_device = MagicMock()
        mock_gpiozero.PWMOutputDevice.return_value = mock_device

        buzzer.start()

        mock_device.off.assert_called_once()

    def test_stop_turns_off_and_closes(self):
        buzzer = Buzzer()
        mock_device = MagicMock()
        buzzer._device = mock_device

        buzzer.stop()

        mock_device.off.assert_called_once()
        mock_device.close.assert_called_once()
        self.assertIsNone(buzzer._device)

    def test_stop_when_not_started(self):
        buzzer = Buzzer()
        buzzer.stop()  # should not raise

    def test_double_stop(self):
        buzzer = Buzzer()
        mock_device = MagicMock()
        buzzer._device = mock_device

        buzzer.stop()
        buzzer.stop()  # second stop should not raise


class TestPlayTone(unittest.TestCase):
    """Tests for single tone playback."""

    def setUp(self):
        self.buzzer = Buzzer()
        self.mock_device = MagicMock()
        self.mock_device.value = 0
        self.buzzer._device = self.mock_device

    def test_play_tone_without_start_raises(self):
        buzzer = Buzzer()
        with self.assertRaises(RuntimeError):
            buzzer.play_tone(440, 0.1)

    def test_play_tone_sets_frequency_and_duty_cycle(self):
        with patch("buzzer.time") as mock_time:
            self.buzzer.play_tone(440, 0.5)

        self.assertEqual(self.mock_device.frequency, 440)
        self.assertEqual(self.mock_device.value, 0.5)

    def test_play_tone_turns_off_after(self):
        with patch("buzzer.time"):
            self.buzzer.play_tone(440, 0.5)

        self.mock_device.off.assert_called()

    def test_play_tone_sleeps_for_duration(self):
        with patch("buzzer.time") as mock_time:
            self.buzzer.play_tone(440, 0.25)

        mock_time.sleep.assert_called_with(0.25)

    def test_rest_does_not_set_frequency(self):
        with patch("buzzer.time") as mock_time:
            self.buzzer.play_tone(REST, 0.1)

        self.mock_device.off.assert_called()
        mock_time.sleep.assert_called_with(0.1)
        # Should not have set frequency or value since it's a rest
        self.assertNotEqual(self.mock_device.value, 0.5)

    def test_zero_frequency_treated_as_rest(self):
        with patch("buzzer.time") as mock_time:
            self.buzzer.play_tone(0, 0.1)

        self.mock_device.off.assert_called()
        mock_time.sleep.assert_called_with(0.1)


class TestPlayMelody(unittest.TestCase):
    """Tests for melody playback."""

    def setUp(self):
        self.buzzer = Buzzer()
        self.mock_device = MagicMock()
        self.mock_device.value = 0
        self.buzzer._device = self.mock_device

    def test_play_melody_without_start_raises(self):
        buzzer = Buzzer()
        with self.assertRaises(RuntimeError):
            buzzer.play_melody([(440, 0.1)])

    def test_play_melody_plays_all_notes(self):
        melody = [(NOTE_C5, 0.1), (NOTE_E5, 0.1), (NOTE_A4, 0.1)]

        with patch("buzzer.time"):
            self.buzzer.play_melody(melody)

        # Should have set frequency 3 times (once per note)
        frequencies_set = [
            c.args[0] if c.args else c[1]
            for c in self.mock_device.mock_calls
            if "frequency" in str(c)
        ]
        # Alternative: just check off was called 3 times (once after each note)
        self.assertEqual(self.mock_device.off.call_count, 3)

    def test_play_empty_melody(self):
        with patch("buzzer.time"):
            self.buzzer.play_melody([])  # should not raise

    def test_play_melody_with_rests(self):
        melody = [(NOTE_C5, 0.1), (REST, 0.05), (NOTE_E5, 0.1)]

        with patch("buzzer.time") as mock_time:
            self.buzzer.play_melody(melody)

        # 3 notes total (including rest), so 3 sleep calls
        self.assertEqual(mock_time.sleep.call_count, 3)


class TestMelodyDuration(unittest.TestCase):
    """Tests for melody_duration helper."""

    def test_simple_melody(self):
        melody = [(440, 0.5), (880, 0.3)]
        self.assertAlmostEqual(melody_duration(melody), 0.8)

    def test_melody_with_rests(self):
        melody = [(440, 0.5), (REST, 0.1), (880, 0.3)]
        self.assertAlmostEqual(melody_duration(melody), 0.9)

    def test_empty_melody(self):
        self.assertAlmostEqual(melody_duration([]), 0.0)


class TestPredefinedMelodies(unittest.TestCase):
    """Validate that all predefined system melodies are well-formed."""

    def _validate_melody(self, melody, name):
        self.assertIsInstance(melody, list, f"{name} should be a list")
        self.assertGreater(len(melody), 0, f"{name} should not be empty")
        for i, note in enumerate(melody):
            self.assertIsInstance(note, tuple, f"{name}[{i}] should be a tuple")
            self.assertEqual(len(note), 2, f"{name}[{i}] should have 2 elements")
            freq, dur = note
            self.assertIsInstance(freq, (int, float), f"{name}[{i}] frequency should be numeric")
            self.assertIsInstance(dur, (int, float), f"{name}[{i}] duration should be numeric")
            self.assertGreaterEqual(freq, 0, f"{name}[{i}] frequency should be >= 0")
            self.assertGreater(dur, 0, f"{name}[{i}] duration should be > 0")

    def test_startup_melody(self):
        self._validate_melody(MELODY_STARTUP, "MELODY_STARTUP")

    def test_arm_melody(self):
        self._validate_melody(MELODY_ARM, "MELODY_ARM")

    def test_disarm_melody(self):
        self._validate_melody(MELODY_DISARM, "MELODY_DISARM")

    def test_sensor_error_melody(self):
        self._validate_melody(MELODY_SENSOR_ERROR, "MELODY_SENSOR_ERROR")

    def test_arm_is_short(self):
        """The arm confirmation should be short and snappy."""
        self.assertLess(melody_duration(MELODY_ARM), 0.5)


class TestMotionMelodyLibrary(unittest.TestCase):
    """Validate the 20-melody motion library."""

    def _validate_melody(self, melody, name):
        self.assertIsInstance(melody, list, f"{name} should be a list")
        self.assertGreater(len(melody), 0, f"{name} should not be empty")
        for i, note in enumerate(melody):
            self.assertIsInstance(note, tuple, f"{name}[{i}] should be a tuple")
            self.assertEqual(len(note), 2, f"{name}[{i}] should have 2 elements")
            freq, dur = note
            self.assertIsInstance(freq, (int, float), f"{name}[{i}] freq should be numeric")
            self.assertIsInstance(dur, (int, float), f"{name}[{i}] dur should be numeric")
            self.assertGreaterEqual(freq, 0, f"{name}[{i}] freq should be >= 0")
            self.assertGreater(dur, 0, f"{name}[{i}] dur should be > 0")

    def test_library_has_20_melodies(self):
        self.assertEqual(len(MOTION_MELODIES), 20)

    def test_all_melodies_have_name_and_notes(self):
        for i, entry in enumerate(MOTION_MELODIES):
            self.assertIsInstance(entry, tuple, f"entry {i} should be a tuple")
            self.assertEqual(len(entry), 2, f"entry {i} should have (name, notes)")
            name, notes = entry
            self.assertIsInstance(name, str, f"entry {i} name should be str")
            self.assertGreater(len(name), 0, f"entry {i} name should not be empty")

    def test_all_melodies_are_well_formed(self):
        for name, notes in MOTION_MELODIES:
            self._validate_melody(notes, name)

    def test_all_names_are_unique(self):
        names = [name for name, _ in MOTION_MELODIES]
        self.assertEqual(len(names), len(set(names)), "melody names should be unique")

    def test_melodies_are_reasonable_length(self):
        """Each melody should be between 1 and 6 seconds."""
        for name, notes in MOTION_MELODIES:
            dur = melody_duration(notes)
            self.assertGreater(dur, 1.0, f"{name} is too short ({dur:.1f}s)")
            self.assertLess(dur, 6.0, f"{name} is too long ({dur:.1f}s)")

    def test_get_random_melody_returns_valid(self):
        name, notes = get_random_melody()
        self.assertIsInstance(name, str)
        self.assertIsInstance(notes, list)
        self.assertGreater(len(notes), 0)


if __name__ == "__main__":
    unittest.main()
