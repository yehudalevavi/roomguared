#!/usr/bin/env python3
"""
Unit tests for the Room Guard web application.

Tests Flask routes with mocked hardware.
Run with: python3 -m pytest tests/test_web_unit.py -v
"""

import json
import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock hardware libraries before importing
sys.modules["gpiozero"] = MagicMock()

sys.path.insert(0, "src")

# Mock the Buzzer hardware so RoomGuard can be instantiated
with patch("buzzer.time"):
    from web_app import app, guard


class TestWebApp(unittest.TestCase):
    """Tests for Flask routes."""

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        # Reset guard state
        guard._armed = False
        guard._led_on = False
        guard._playing = False
        guard._motion_count = 0
        guard._last_event_time = None
        guard._event_log = []

    def test_index_returns_html(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Room Guard", r.data)

    def test_status_returns_json(self):
        r = self.client.get("/api/status")
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertIn("armed", d)
        self.assertIn("led_on", d)
        self.assertIn("motion_count", d)

    def test_status_default_values(self):
        d = json.loads(self.client.get("/api/status").data)
        self.assertFalse(d["armed"])
        self.assertFalse(d["led_on"])
        self.assertFalse(d["playing"])
        self.assertEqual(d["motion_count"], 0)

    def test_arm(self):
        r = self.client.post("/api/arm")
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertTrue(d["armed"])
        # Verify state
        self.assertTrue(guard._armed)

    def test_disarm(self):
        guard._armed = True
        r = self.client.post("/api/disarm")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertFalse(d["armed"])
        self.assertFalse(guard._armed)

    def test_led_on(self):
        r = self.client.post("/api/led/on")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertTrue(d["led_on"])
        self.assertTrue(guard._led_on)

    def test_led_off(self):
        guard._led_on = True
        r = self.client.post("/api/led/off")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertFalse(d["led_on"])
        self.assertFalse(guard._led_on)

    def test_melodies_returns_list(self):
        r = self.client.get("/api/melodies")
        d = json.loads(r.data)
        self.assertIn("melodies", d)
        self.assertEqual(len(d["melodies"]), 20)
        self.assertIn("Twinkle Twinkle Little Star", d["melodies"])

    def test_play_valid_melody(self):
        r = self.client.post("/api/play/Ode to Joy")
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_play_invalid_melody(self):
        r = self.client.post("/api/play/NonExistentMelody")
        self.assertEqual(r.status_code, 404)
        d = json.loads(r.data)
        self.assertFalse(d["ok"])

    def test_logs_empty(self):
        r = self.client.get("/api/logs")
        d = json.loads(r.data)
        self.assertIn("logs", d)
        self.assertIsInstance(d["logs"], list)

    def test_logs_with_entries(self):
        guard._event_log = [
            {"time": "2026-03-11 10:00:00", "message": "Test event 1"},
            {"time": "2026-03-11 10:00:01", "message": "Test event 2"},
        ]
        r = self.client.get("/api/logs?limit=10")
        d = json.loads(r.data)
        self.assertEqual(len(d["logs"]), 2)
        # Most recent first
        self.assertEqual(d["logs"][0]["message"], "Test event 2")

    def test_logs_limit(self):
        guard._event_log = [
            {"time": f"2026-03-11 10:00:{i:02d}", "message": f"Event {i}"}
            for i in range(20)
        ]
        r = self.client.get("/api/logs?limit=5")
        d = json.loads(r.data)
        self.assertEqual(len(d["logs"]), 5)


class TestRoomGuardClass(unittest.TestCase):
    """Tests for the RoomGuard class logic (no hardware)."""

    def setUp(self):
        guard._armed = False
        guard._led_on = False
        guard._playing = False
        guard._motion_count = 0
        guard._last_event_time = None
        guard._event_log = []

    def test_arm_disarm_toggle(self):
        guard.arm()
        self.assertTrue(guard._armed)
        guard.disarm()
        self.assertFalse(guard._armed)

    def test_double_arm_is_noop(self):
        guard.arm()
        guard.arm()  # should not raise
        self.assertTrue(guard._armed)

    def test_double_disarm_is_noop(self):
        guard.disarm()
        guard.disarm()  # should not raise
        self.assertFalse(guard._armed)

    def test_set_led(self):
        guard.set_led(True)
        self.assertTrue(guard._led_on)
        guard.set_led(False)
        self.assertFalse(guard._led_on)

    def test_get_melody_names(self):
        names = guard.get_melody_names()
        self.assertEqual(len(names), 20)
        self.assertIsInstance(names[0], str)

    def test_get_status_keys(self):
        status = guard.get_status()
        for key in ("armed", "led_on", "playing", "motion_count", "last_event", "cooldown"):
            self.assertIn(key, status)

    def test_log_message_adds_entry(self):
        guard._log_message("test message")
        self.assertEqual(len(guard._event_log), 1)
        self.assertEqual(guard._event_log[0]["message"], "test message")

    def test_log_max_entries_trimmed(self):
        for i in range(150):
            guard._log_message(f"msg {i}")
        self.assertLessEqual(len(guard._event_log), 100)


if __name__ == "__main__":
    unittest.main()
