#!/usr/bin/env python3
"""
Integration tests for RoomGuard media (Bluetooth + Spotify).

Tests that RoomGuard properly delegates to BluetoothSpeaker and
SpotifyPlayer, and degrades gracefully when they are unavailable.
Run with: python3 -m pytest tests/test_media_integration.py -v
"""

import sys
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# Mock hardware libraries before importing
sys.modules["gpiozero"] = MagicMock()
sys.modules["spotipy"] = MagicMock()
sys.modules["spotipy.oauth2"] = MagicMock()

sys.path.insert(0, "src")

with patch("buzzer.time"):
    from room_guard import RoomGuard


class TestRoomGuardMediaInit(unittest.TestCase):
    """Tests that RoomGuard creates media module instances."""

    def test_has_bluetooth_speaker(self):
        guard = RoomGuard()
        self.assertIsNotNone(guard._bt_speaker)

    def test_has_spotify_player(self):
        guard = RoomGuard()
        self.assertIsNotNone(guard._spotify)


class TestRoomGuardMediaStatus(unittest.TestCase):
    """Tests for media fields in get_status()."""

    def setUp(self):
        self.guard = RoomGuard()
        self.guard._bt_speaker = MagicMock()
        self.guard._spotify = MagicMock()

    def test_status_includes_bt_connected(self):
        self.guard._bt_speaker.get_status.return_value = {"connected": True}
        self.guard._spotify.is_authenticated.return_value = False
        status = self.guard.get_status()
        self.assertIn("bt_connected", status)
        self.assertTrue(status["bt_connected"])

    def test_status_includes_spotify_authenticated(self):
        self.guard._bt_speaker.get_status.return_value = {"connected": False}
        self.guard._spotify.is_authenticated.return_value = True
        status = self.guard.get_status()
        self.assertIn("spotify_authenticated", status)
        self.assertTrue(status["spotify_authenticated"])

    def test_status_bt_exception_defaults_false(self):
        self.guard._bt_speaker.get_status.side_effect = Exception("fail")
        self.guard._spotify.is_authenticated.return_value = False
        status = self.guard.get_status()
        self.assertFalse(status["bt_connected"])

    def test_status_spotify_exception_defaults_false(self):
        self.guard._bt_speaker.get_status.return_value = {"connected": False}
        self.guard._spotify.is_authenticated.side_effect = Exception("fail")
        status = self.guard.get_status()
        self.assertFalse(status["spotify_authenticated"])


class TestRoomGuardGetBtStatus(unittest.TestCase):
    """Tests for get_bt_status()."""

    def setUp(self):
        self.guard = RoomGuard()
        self.guard._bt_speaker = MagicMock()

    def test_delegates_to_bt_speaker(self):
        expected = {"connected": True, "device_name": "JBL"}
        self.guard._bt_speaker.get_status.return_value = expected
        result = self.guard.get_bt_status()
        self.assertEqual(result, expected)


class TestRoomGuardGetSpotifyStatus(unittest.TestCase):
    """Tests for get_spotify_status()."""

    def setUp(self):
        self.guard = RoomGuard()
        self.guard._spotify = MagicMock()

    def test_not_authenticated(self):
        self.guard._spotify.is_authenticated.return_value = False
        self.guard._spotify.is_configured.return_value = False
        result = self.guard.get_spotify_status()
        self.assertFalse(result["authenticated"])
        self.assertFalse(result["configured"])

    def test_authenticated_with_playback(self):
        self.guard._spotify.is_authenticated.return_value = True
        self.guard._spotify.is_configured.return_value = True
        self.guard._spotify.get_current_playback.return_value = {
            "track": {"name": "Song", "artist": "Artist"},
            "is_playing": True,
        }
        result = self.guard.get_spotify_status()
        self.assertTrue(result["authenticated"])
        self.assertIsNotNone(result["playback"])


class TestRoomGuardPlayRandomSong(unittest.TestCase):
    """Tests for play_random_song()."""

    def setUp(self):
        self.guard = RoomGuard()
        self.guard._spotify = MagicMock()
        self.guard._lcd = MagicMock()
        self.guard._lcd._lcd = None  # Disable LCD writes

    def test_play_random_song_success(self):
        self.guard._spotify.is_authenticated.return_value = True
        self.guard._spotify.play_random_liked_song.return_value = {
            "name": "Test Song",
            "artist": "Test Artist",
            "uri": "spotify:track:123",
        }
        result = self.guard.play_random_song()
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Test Song")

    def test_play_random_song_not_authenticated(self):
        self.guard._spotify.is_authenticated.return_value = False
        result = self.guard.play_random_song()
        self.assertIsNone(result)

    def test_play_random_song_no_liked_songs(self):
        self.guard._spotify.is_authenticated.return_value = True
        self.guard._spotify.play_random_liked_song.return_value = None
        result = self.guard.play_random_song()
        self.assertIsNone(result)

    def test_play_random_song_exception(self):
        self.guard._spotify.is_authenticated.return_value = True
        self.guard._spotify.play_random_liked_song.side_effect = Exception("API error")
        result = self.guard.play_random_song()
        self.assertIsNone(result)


class TestRoomGuardSpotifyTransport(unittest.TestCase):
    """Tests for Spotify transport control methods."""

    def setUp(self):
        self.guard = RoomGuard()
        self.guard._spotify = MagicMock()
        self.guard._lcd = MagicMock()
        self.guard._lcd._lcd = None

    def test_pause(self):
        self.guard._spotify.pause.return_value = True
        result = self.guard.spotify_pause()
        self.assertTrue(result)
        self.guard._spotify.pause.assert_called_once()

    def test_resume(self):
        self.guard._spotify.resume.return_value = True
        result = self.guard.spotify_resume()
        self.assertTrue(result)
        self.guard._spotify.resume.assert_called_once()

    def test_next(self):
        self.guard._spotify.next_track.return_value = True
        result = self.guard.spotify_next()
        self.assertTrue(result)
        self.guard._spotify.next_track.assert_called_once()

    def test_prev(self):
        self.guard._spotify.prev_track.return_value = True
        result = self.guard.spotify_prev()
        self.assertTrue(result)
        self.guard._spotify.prev_track.assert_called_once()

    def test_volume(self):
        self.guard._spotify.set_volume.return_value = True
        result = self.guard.spotify_volume(50)
        self.assertTrue(result)
        self.guard._spotify.set_volume.assert_called_once_with(50)

    def test_pause_exception(self):
        self.guard._spotify.pause.side_effect = Exception("fail")
        result = self.guard.spotify_pause()
        self.assertFalse(result)

    def test_resume_exception(self):
        self.guard._spotify.resume.side_effect = Exception("fail")
        result = self.guard.spotify_resume()
        self.assertFalse(result)

    def test_next_exception(self):
        self.guard._spotify.next_track.side_effect = Exception("fail")
        result = self.guard.spotify_next()
        self.assertFalse(result)

    def test_prev_exception(self):
        self.guard._spotify.prev_track.side_effect = Exception("fail")
        result = self.guard.spotify_prev()
        self.assertFalse(result)

    def test_volume_exception(self):
        self.guard._spotify.set_volume.side_effect = Exception("fail")
        result = self.guard.spotify_volume(50)
        self.assertFalse(result)


class TestRoomGuardLCDPages(unittest.TestCase):
    """Tests for the Now Playing LCD page."""

    def setUp(self):
        self.guard = RoomGuard()
        self.guard._spotify = MagicMock()
        self.guard._bt_speaker = MagicMock()

    def test_page3_with_spotify_playing(self):
        self.guard._spotify.is_authenticated.return_value = True
        self.guard._spotify.get_current_playback.return_value = {
            "is_playing": True,
            "track": {"name": "Cool Song", "artist": "Cool Artist"},
        }
        line1 = self.guard._lcd_page_line1(3)
        self.assertIn("Cool Song", line1)
        self.assertIn("Cool Artist", line1)

    def test_page3_nothing_playing(self):
        self.guard._spotify.is_authenticated.return_value = True
        self.guard._spotify.get_current_playback.return_value = None
        line1 = self.guard._lcd_page_line1(3)
        self.assertEqual(line1, "No music playing")

    def test_page3_not_authenticated(self):
        self.guard._spotify.is_authenticated.return_value = False
        line1 = self.guard._lcd_page_line1(3)
        self.assertEqual(line1, "No music playing")

    def test_page3_line2_bt_connected(self):
        self.guard._bt_speaker.get_status.return_value = {
            "connected": True,
            "device_name": "JBL Flip 7",
        }
        line2 = self.guard._lcd_page_line2(3)
        self.assertIn("BT:", line2)
        self.assertIn("JBL Flip 7", line2)

    def test_page3_line2_bt_not_connected(self):
        self.guard._bt_speaker.get_status.return_value = {"connected": False}
        line2 = self.guard._lcd_page_line2(3)
        # Falls back to clock format
        self.assertNotIn("BT:", line2)


if __name__ == "__main__":
    unittest.main()
