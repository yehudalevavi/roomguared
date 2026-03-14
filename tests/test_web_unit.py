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

    def test_lcd_message_both_lines(self):
        r = self.client.post(
            "/api/lcd/message",
            data=json.dumps({"line1": "Hello", "line2": "World"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertEqual(d["line1"], "Hello")
        self.assertEqual(d["line2"], "World")

    def test_lcd_message_line1_only(self):
        r = self.client.post(
            "/api/lcd/message",
            data=json.dumps({"line1": "Just line 1"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_lcd_message_empty_rejected(self):
        r = self.client.post(
            "/api/lcd/message",
            data=json.dumps({"line1": "", "line2": ""}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        d = json.loads(r.data)
        self.assertFalse(d["ok"])

    def test_lcd_message_rejects_unicode(self):
        r = self.client.post(
            "/api/lcd/message",
            data=json.dumps({"line1": "שלום עולם", "line2": ""}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        d = json.loads(r.data)
        self.assertFalse(d["ok"])
        self.assertIn("Unsupported", d["error"])

    def test_lcd_message_rejects_emoji(self):
        r = self.client.post(
            "/api/lcd/message",
            data=json.dumps({"line1": "Hello 🎵"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)

    def test_lcd_message_rejects_control_chars(self):
        r = self.client.post(
            "/api/lcd/message",
            data=json.dumps({"line1": "line1\nline2"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)

    def test_lcd_message_truncates_long_lines(self):
        r = self.client.post(
            "/api/lcd/message",
            data=json.dumps({"line1": "ABCDEFGHIJKLMNOPQRST"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertEqual(len(d["line1"]), 16)


    def test_melody_next_endpoint(self):
        r = self.client.post("/api/melody/next")
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertIn("melody", d)

    def test_melody_prev_endpoint(self):
        r = self.client.post("/api/melody/prev")
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertIn("melody", d)

    def test_melody_play_endpoint(self):
        r = self.client.post("/api/melody/play")
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertIn("melody", d)

    def test_melody_stop_endpoint(self):
        guard._playing = True
        r = self.client.post("/api/melody/stop")
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_toggle_arm_endpoint(self):
        r = self.client.post("/api/toggle-arm")
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertIn("armed", d)

    def test_nfc_cards_no_reader(self):
        r = self.client.get("/api/nfc/cards")
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertFalse(d["available"])

    def test_nfc_scan_no_reader(self):
        r = self.client.post("/api/nfc/scan")
        self.assertEqual(r.status_code, 503)

    def test_nfc_scan_start_no_reader(self):
        r = self.client.post("/api/nfc/scan/start")
        self.assertEqual(r.status_code, 503)

    def test_nfc_scan_result_no_reader(self):
        r = self.client.get("/api/nfc/scan/result")
        self.assertEqual(r.status_code, 503)

    def test_nfc_register_no_reader(self):
        r = self.client.post(
            "/api/nfc/register",
            data=json.dumps({"uid": "0x123", "action": "toggle_arm"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 503)

    def test_nfc_last_scan_no_reader(self):
        r = self.client.get("/api/nfc/last-scan")
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertFalse(d["available"])


class TestRoomGuardClass(unittest.TestCase):
    """Tests for the RoomGuard class logic (no hardware)."""

    def setUp(self):
        guard._armed = False
        guard._led_on = False
        guard._playing = False
        guard._motion_count = 0
        guard._last_event_time = None
        guard._event_log = []
        guard._melody_index = 0

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

    def test_next_melody(self):
        name = guard.next_melody()
        self.assertEqual(guard._melody_index, 1)
        self.assertIsInstance(name, str)
        self.assertGreater(len(name), 0)

    def test_prev_melody(self):
        guard._melody_index = 5
        name = guard.prev_melody()
        self.assertEqual(guard._melody_index, 4)
        self.assertIsInstance(name, str)

    def test_next_melody_wraps_around(self):
        guard._melody_index = 19
        name = guard.next_melody()
        self.assertEqual(guard._melody_index, 0)

    def test_prev_melody_wraps_around(self):
        guard._melody_index = 0
        name = guard.prev_melody()
        self.assertEqual(guard._melody_index, 19)

    def test_get_current_melody(self):
        guard._melody_index = 3
        idx, name = guard.get_current_melody()
        self.assertEqual(idx, 3)
        self.assertIsInstance(name, str)

    def test_play_current_melody(self):
        name = guard.play_current_melody()
        self.assertIsInstance(name, str)

    def test_stop_melody_clears_playing(self):
        guard._playing = True
        guard.stop_melody()
        self.assertFalse(guard._playing)

    def test_toggle_arm_arms_when_disarmed(self):
        guard._armed = False
        result = guard.toggle_arm()
        self.assertTrue(result)
        self.assertTrue(guard._armed)

    def test_toggle_arm_disarms_when_armed(self):
        guard._armed = True
        result = guard.toggle_arm()
        self.assertFalse(result)
        self.assertFalse(guard._armed)

    def test_status_includes_current_melody(self):
        status = guard.get_status()
        self.assertIn("current_melody", status)
        self.assertIn("current_melody_index", status)
        self.assertEqual(status["current_melody_index"], 0)

    def test_next_then_status_reflects_change(self):
        guard.next_melody()
        status = guard.get_status()
        self.assertEqual(status["current_melody_index"], 1)


class TestBluetoothAPI(unittest.TestCase):
    """Tests for Bluetooth REST API endpoints."""

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        guard._bt_speaker = MagicMock()

    def test_bt_status(self):
        guard._bt_speaker.get_status.return_value = {
            "connected": False, "paired": False,
            "device_name": None, "device_address": None,
        }
        r = self.client.get("/api/bluetooth/status")
        self.assertEqual(r.status_code, 200)
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertIn("connected", d)

    def test_bt_scan(self):
        guard._bt_speaker.scan.return_value = [
            {"address": "AA:BB:CC:DD:EE:FF", "name": "JBL", "paired": False, "connected": False}
        ]
        r = self.client.post("/api/bluetooth/scan",
                             data=json.dumps({"timeout": 5}),
                             content_type="application/json")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertEqual(len(d["devices"]), 1)

    def test_bt_pair(self):
        guard._bt_speaker.pair.return_value = True
        guard._bt_speaker.get_status.return_value = {"connected": True, "paired": True, "device_name": "JBL", "device_address": "AA:BB"}
        r = self.client.post("/api/bluetooth/pair",
                             data=json.dumps({"address": "AA:BB:CC:DD:EE:FF"}),
                             content_type="application/json")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_bt_pair_no_address(self):
        r = self.client.post("/api/bluetooth/pair",
                             data=json.dumps({}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_bt_connect(self):
        guard._bt_speaker.connect.return_value = True
        guard._bt_speaker.get_status.return_value = {"connected": True, "paired": True, "device_name": "JBL", "device_address": "AA:BB"}
        r = self.client.post("/api/bluetooth/connect",
                             data=json.dumps({"address": "AA:BB:CC:DD:EE:FF"}),
                             content_type="application/json")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_bt_disconnect(self):
        guard._bt_speaker.disconnect.return_value = True
        guard._bt_speaker.get_status.return_value = {"connected": False, "paired": True, "device_name": "JBL", "device_address": "AA:BB"}
        r = self.client.post("/api/bluetooth/disconnect")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_bt_remove(self):
        guard._bt_speaker.remove.return_value = True
        r = self.client.delete("/api/bluetooth/device/AA:BB:CC:DD:EE:FF")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])


class TestSpotifyAPI(unittest.TestCase):
    """Tests for Spotify REST API endpoints."""

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        guard._spotify = MagicMock()
        guard._bt_speaker = MagicMock()
        guard._bt_speaker.get_status.return_value = {"connected": False}
        guard._lcd = MagicMock()
        guard._lcd._lcd = None

    def test_spotify_status(self):
        guard._spotify.is_authenticated.return_value = False
        guard._spotify.is_configured.return_value = False
        r = self.client.get("/api/spotify/status")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertIn("authenticated", d)

    def test_spotify_credentials(self):
        r = self.client.post("/api/spotify/credentials",
                             data=json.dumps({"client_id": "id", "client_secret": "secret"}),
                             content_type="application/json")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        guard._spotify.set_credentials.assert_called_once_with("id", "secret")

    def test_spotify_credentials_missing(self):
        r = self.client.post("/api/spotify/credentials",
                             data=json.dumps({}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_spotify_auth(self):
        guard._spotify.get_auth_url.return_value = "https://accounts.spotify.com/authorize?..."
        r = self.client.get("/api/spotify/auth")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertIn("auth_url", d)

    def test_spotify_auth_not_configured(self):
        guard._spotify.get_auth_url.return_value = None
        r = self.client.get("/api/spotify/auth")
        self.assertEqual(r.status_code, 400)

    def test_spotify_callback_success(self):
        guard._spotify.handle_auth_callback.return_value = True
        r = self.client.get("/api/spotify/callback?code=test_code")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"connected", r.data)

    def test_spotify_callback_error(self):
        r = self.client.get("/api/spotify/callback?error=access_denied")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"denied", r.data)

    def test_spotify_callback_no_code(self):
        r = self.client.get("/api/spotify/callback")
        self.assertEqual(r.status_code, 400)

    def test_spotify_play_random(self):
        guard._spotify.is_authenticated.return_value = True
        guard._spotify.play_random_liked_song.return_value = {
            "name": "Song", "artist": "Artist", "uri": "spotify:track:123",
        }
        r = self.client.post("/api/spotify/play-random")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertIn("track", d)

    def test_spotify_play_random_fail(self):
        guard._spotify.is_authenticated.return_value = False
        r = self.client.post("/api/spotify/play-random")
        self.assertEqual(r.status_code, 500)

    def test_spotify_play_uri(self):
        guard._spotify.play_track.return_value = True
        r = self.client.post("/api/spotify/play",
                             data=json.dumps({"uri": "spotify:track:abc"}),
                             content_type="application/json")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_spotify_play_uri_missing(self):
        r = self.client.post("/api/spotify/play",
                             data=json.dumps({}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_spotify_pause(self):
        guard._spotify.pause.return_value = True
        r = self.client.post("/api/spotify/pause")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_spotify_resume(self):
        guard._spotify.resume.return_value = True
        r = self.client.post("/api/spotify/resume")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_spotify_next(self):
        guard._spotify.next_track.return_value = True
        r = self.client.post("/api/spotify/next")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_spotify_prev(self):
        guard._spotify.prev_track.return_value = True
        r = self.client.post("/api/spotify/prev")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_spotify_volume(self):
        guard._spotify.set_volume.return_value = True
        r = self.client.post("/api/spotify/volume",
                             data=json.dumps({"percent": 75}),
                             content_type="application/json")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_spotify_volume_missing(self):
        r = self.client.post("/api/spotify/volume",
                             data=json.dumps({}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_spotify_devices(self):
        guard._spotify.get_devices.return_value = [
            {"id": "d1", "name": "Room Guard", "type": "Computer", "is_active": True}
        ]
        r = self.client.get("/api/spotify/devices")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])
        self.assertEqual(len(d["devices"]), 1)

    def test_spotify_transfer(self):
        guard._spotify.transfer_playback.return_value = True
        r = self.client.post("/api/spotify/transfer",
                             data=json.dumps({"device_id": "dev123"}),
                             content_type="application/json")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_spotify_transfer_missing_device(self):
        r = self.client.post("/api/spotify/transfer",
                             data=json.dumps({}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)


class TestNFCNewActions(unittest.TestCase):
    """Tests for new NFC music actions in the register endpoint."""

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        # Import and set up nfc_reader module-level var
        import web_app
        self.mock_nfc = MagicMock()
        web_app.nfc_reader = self.mock_nfc

    def test_register_play_random_song_action(self):
        r = self.client.post("/api/nfc/register",
                             data=json.dumps({"uid": "0xABC", "action": "play_random_song", "label": "Music card"}),
                             content_type="application/json")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_register_spotify_pause_action(self):
        r = self.client.post("/api/nfc/register",
                             data=json.dumps({"uid": "0xDEF", "action": "spotify_pause"}),
                             content_type="application/json")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_register_spotify_next_action(self):
        r = self.client.post("/api/nfc/register",
                             data=json.dumps({"uid": "0x111", "action": "spotify_next"}),
                             content_type="application/json")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def test_register_play_track_action(self):
        r = self.client.post("/api/nfc/register",
                             data=json.dumps({"uid": "0x222", "action": "play_track:spotify:track:abc"}),
                             content_type="application/json")
        d = json.loads(r.data)
        self.assertTrue(d["ok"])

    def tearDown(self):
        import web_app
        web_app.nfc_reader = None


if __name__ == "__main__":
    unittest.main()
