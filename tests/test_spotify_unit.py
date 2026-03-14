#!/usr/bin/env python3
"""
Unit tests for the Spotify player module.

Mocks the spotipy library so tests run anywhere without Spotify credentials.
Run with: python3 -m pytest tests/test_spotify_unit.py -v
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# Mock spotipy before importing our module
mock_spotipy = MagicMock()
sys.modules["spotipy"] = mock_spotipy
sys.modules["spotipy.oauth2"] = MagicMock()

sys.path.insert(0, "src")
from spotify_player import SpotifyPlayer, _JsonCacheHandler, SCOPES, DEFAULT_REDIRECT_URI


class TestSpotifyPlayerInit(unittest.TestCase):
    """Tests for initialization."""

    def test_default_state(self):
        sp = SpotifyPlayer(config_path="/nonexistent/path.json")
        self.assertFalse(sp._started)
        self.assertIsNone(sp._sp)
        self.assertIsNone(sp._auth_manager)
        self.assertEqual(sp._config, {})

    def test_not_authenticated_before_start(self):
        sp = SpotifyPlayer(config_path="/nonexistent/path.json")
        self.assertFalse(sp.is_authenticated())

    def test_not_configured_without_credentials(self):
        sp = SpotifyPlayer(config_path="/nonexistent/path.json")
        self.assertFalse(sp.is_configured())


class TestSpotifyPlayerLifecycle(unittest.TestCase):
    """Tests for start/stop lifecycle."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "spotify.json")

    def test_start_without_credentials(self):
        sp = SpotifyPlayer(config_path=self.config_path)
        sp.start()
        self.assertTrue(sp._started)
        self.assertIsNone(sp._auth_manager)
        self.assertIsNone(sp._sp)

    def test_start_with_credentials_inits_client(self):
        config = {
            "client_id": "test_id",
            "client_secret": "test_secret",
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f)

        sp = SpotifyPlayer(config_path=self.config_path)
        sp.start()
        self.assertTrue(sp._started)
        # auth_manager should be initialized
        self.assertIsNotNone(sp._auth_manager)

    def test_stop(self):
        sp = SpotifyPlayer(config_path=self.config_path)
        sp.start()
        sp.stop()
        self.assertFalse(sp._started)
        self.assertIsNone(sp._sp)
        self.assertIsNone(sp._auth_manager)


class TestSpotifyPlayerCredentials(unittest.TestCase):
    """Tests for credential management."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "spotify.json")
        self.sp = SpotifyPlayer(config_path=self.config_path)

    def test_set_credentials_saves_to_config(self):
        self.sp.set_credentials("my_id", "my_secret")

        with open(self.config_path, "r") as f:
            data = json.load(f)
        self.assertEqual(data["client_id"], "my_id")
        self.assertEqual(data["client_secret"], "my_secret")

    def test_set_credentials_makes_configured(self):
        self.sp.set_credentials("my_id", "my_secret")
        self.assertTrue(self.sp.is_configured())

    def test_set_credentials_reinits_when_started(self):
        self.sp._started = True
        with patch.object(self.sp, "_init_client") as mock_init:
            self.sp.set_credentials("my_id", "my_secret")
            mock_init.assert_called_once()


class TestSpotifyPlayerAuth(unittest.TestCase):
    """Tests for OAuth2 authentication flow."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "spotify.json")
        self.sp = SpotifyPlayer(config_path=self.config_path)
        self.sp._started = True

    def test_get_auth_url_without_auth_manager(self):
        self.sp._auth_manager = None
        result = self.sp.get_auth_url()
        self.assertIsNone(result)

    def test_get_auth_url_with_auth_manager(self):
        mock_am = MagicMock()
        mock_am.get_authorize_url.return_value = "https://accounts.spotify.com/authorize?..."
        self.sp._auth_manager = mock_am

        url = self.sp.get_auth_url()
        self.assertEqual(url, "https://accounts.spotify.com/authorize?...")

    def test_get_auth_url_not_started_raises(self):
        self.sp._started = False
        with self.assertRaises(RuntimeError):
            self.sp.get_auth_url()

    def test_handle_auth_callback_success(self):
        mock_am = MagicMock()
        mock_am.get_access_token.return_value = {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_at": 9999999999,
        }
        self.sp._auth_manager = mock_am

        with patch.object(self.sp, "_save_tokens"):
            with patch.object(self.sp, "_init_client"):
                result = self.sp.handle_auth_callback("auth_code_123")

        self.assertTrue(result)
        mock_am.get_access_token.assert_called_once_with("auth_code_123", as_dict=True)

    def test_handle_auth_callback_failure(self):
        mock_am = MagicMock()
        mock_am.get_access_token.side_effect = Exception("Bad code")
        self.sp._auth_manager = mock_am

        result = self.sp.handle_auth_callback("bad_code")
        self.assertFalse(result)

    def test_handle_auth_callback_no_auth_manager(self):
        self.sp._auth_manager = None
        result = self.sp.handle_auth_callback("code")
        self.assertFalse(result)


class TestSpotifyPlayerTransport(unittest.TestCase):
    """Tests for playback transport controls."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "spotify.json")
        self.sp = SpotifyPlayer(config_path=self.config_path)
        self.sp._started = True
        self.sp._sp = MagicMock()

    def test_pause(self):
        result = self.sp.pause()
        self.assertTrue(result)
        self.sp._sp.pause_playback.assert_called_once()

    def test_pause_failure(self):
        self.sp._sp.pause_playback.side_effect = Exception("No active device")
        result = self.sp.pause()
        self.assertFalse(result)

    def test_resume(self):
        self.sp._sp.devices.return_value = {
            "devices": [{"id": "dev1", "name": "Room Guard"}]
        }
        result = self.sp.resume()
        self.assertTrue(result)
        self.sp._sp.start_playback.assert_called_once()

    def test_next_track(self):
        result = self.sp.next_track()
        self.assertTrue(result)
        self.sp._sp.next_track.assert_called_once()

    def test_prev_track(self):
        result = self.sp.prev_track()
        self.assertTrue(result)
        self.sp._sp.previous_track.assert_called_once()

    def test_set_volume(self):
        result = self.sp.set_volume(75)
        self.assertTrue(result)
        self.sp._sp.volume.assert_called_once_with(75)

    def test_set_volume_clamped_high(self):
        self.sp.set_volume(150)
        self.sp._sp.volume.assert_called_once_with(100)

    def test_set_volume_clamped_low(self):
        self.sp.set_volume(-10)
        self.sp._sp.volume.assert_called_once_with(0)

    def test_transport_not_started_raises(self):
        self.sp._started = False
        with self.assertRaises(RuntimeError):
            self.sp.pause()

    def test_transport_not_authenticated_raises(self):
        self.sp._sp = None
        with self.assertRaises(RuntimeError):
            self.sp.pause()


class TestSpotifyPlayerPlayback(unittest.TestCase):
    """Tests for track playback and liked songs."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "spotify.json")
        self.sp = SpotifyPlayer(config_path=self.config_path)
        self.sp._started = True
        self.sp._sp = MagicMock()

    def _make_track(self, name="Test Song", artist="Test Artist", uri="spotify:track:123"):
        return {
            "uri": uri,
            "name": name,
            "duration_ms": 200000,
            "artists": [{"name": artist}],
            "album": {
                "name": "Test Album",
                "images": [{"url": "https://example.com/art.jpg"}],
            },
        }

    def test_get_liked_songs(self):
        self.sp._sp.current_user_saved_tracks.return_value = {
            "items": [{"track": self._make_track()}],
            "total": 100,
        }

        songs = self.sp.get_liked_songs(limit=10)
        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0]["name"], "Test Song")
        self.assertEqual(songs[0]["artist"], "Test Artist")
        self.assertEqual(songs[0]["album"], "Test Album")
        self.assertIsNotNone(songs[0]["album_art"])
        self.assertEqual(self.sp._liked_songs_total, 100)

    def test_get_liked_songs_empty(self):
        self.sp._sp.current_user_saved_tracks.return_value = {
            "items": [], "total": 0
        }
        songs = self.sp.get_liked_songs()
        self.assertEqual(songs, [])

    def test_get_liked_songs_count(self):
        self.sp._sp.current_user_saved_tracks.return_value = {"total": 42}
        count = self.sp.get_liked_songs_count()
        self.assertEqual(count, 42)

    def test_play_track(self):
        self.sp._sp.devices.return_value = {
            "devices": [{"id": "dev1", "name": "Room Guard"}]
        }
        result = self.sp.play_track("spotify:track:abc")
        self.assertTrue(result)
        self.sp._sp.start_playback.assert_called_once_with(
            device_id="dev1", uris=["spotify:track:abc"]
        )

    def test_play_track_failure(self):
        self.sp._sp.devices.return_value = {"devices": []}
        self.sp._sp.start_playback.side_effect = Exception("No device")
        result = self.sp.play_track("spotify:track:abc")
        self.assertFalse(result)

    @patch("spotify_player.random.randint", return_value=5)
    def test_play_random_liked_song(self, mock_randint):
        track = self._make_track()
        self.sp._sp.current_user_saved_tracks.side_effect = [
            {"total": 50},  # count call
            {"items": [{"track": track}]},  # random offset call
        ]
        self.sp._sp.devices.return_value = {
            "devices": [{"id": "dev1", "name": "Room Guard"}]
        }

        result = self.sp.play_random_liked_song()
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Test Song")
        self.sp._sp.start_playback.assert_called_once()

    def test_play_random_no_liked_songs(self):
        self.sp._sp.current_user_saved_tracks.return_value = {"total": 0}
        result = self.sp.play_random_liked_song()
        self.assertIsNone(result)


class TestSpotifyPlayerCurrentPlayback(unittest.TestCase):
    """Tests for current playback info."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "spotify.json")
        self.sp = SpotifyPlayer(config_path=self.config_path)
        self.sp._started = True
        self.sp._sp = MagicMock()

    def test_get_current_playback(self):
        self.sp._sp.current_playback.return_value = {
            "is_playing": True,
            "progress_ms": 30000,
            "item": {
                "uri": "spotify:track:xyz",
                "name": "Now Playing",
                "duration_ms": 180000,
                "artists": [{"name": "Artist"}],
                "album": {"name": "Album", "images": [{"url": "https://art.jpg"}]},
            },
            "device": {"name": "Room Guard", "volume_percent": 65},
        }

        playback = self.sp.get_current_playback()
        self.assertIsNotNone(playback)
        self.assertTrue(playback["is_playing"])
        self.assertEqual(playback["track"]["name"], "Now Playing")
        self.assertEqual(playback["progress_ms"], 30000)
        self.assertEqual(playback["volume_percent"], 65)

    def test_get_current_playback_nothing_playing(self):
        self.sp._sp.current_playback.return_value = None
        playback = self.sp.get_current_playback()
        self.assertIsNone(playback)

    def test_get_current_playback_no_item(self):
        self.sp._sp.current_playback.return_value = {"item": None}
        playback = self.sp.get_current_playback()
        self.assertIsNone(playback)


class TestSpotifyPlayerDevices(unittest.TestCase):
    """Tests for Spotify Connect device management."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "spotify.json")
        self.sp = SpotifyPlayer(config_path=self.config_path)
        self.sp._started = True
        self.sp._sp = MagicMock()

    def test_get_devices(self):
        self.sp._sp.devices.return_value = {
            "devices": [
                {"id": "d1", "name": "Room Guard", "type": "Computer", "is_active": True, "volume_percent": 50},
                {"id": "d2", "name": "Phone", "type": "Smartphone", "is_active": False, "volume_percent": 100},
            ]
        }
        devices = self.sp.get_devices()
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]["name"], "Room Guard")
        self.assertTrue(devices[0]["is_active"])

    def test_get_devices_empty(self):
        self.sp._sp.devices.return_value = {"devices": []}
        devices = self.sp.get_devices()
        self.assertEqual(devices, [])

    def test_transfer_playback(self):
        result = self.sp.transfer_playback("device_123")
        self.assertTrue(result)
        self.sp._sp.transfer_playback.assert_called_once_with("device_123", force_play=True)

    def test_get_pi_device_id_found(self):
        self.sp._sp.devices.return_value = {
            "devices": [
                {"id": "d1", "name": "Phone"},
                {"id": "d2", "name": "Room Guard"},
            ]
        }
        device_id = self.sp._get_pi_device_id()
        self.assertEqual(device_id, "d2")

    def test_get_pi_device_id_no_fallback_to_other_devices(self):
        """Should return None when only non-Pi devices are available."""
        self.sp._sp.devices.return_value = {
            "devices": [{"id": "d1", "name": "Phone"}]
        }
        device_id = self.sp._get_pi_device_id()
        self.assertIsNone(device_id)

    def test_get_pi_device_id_none(self):
        self.sp._sp.devices.return_value = {"devices": []}
        device_id = self.sp._get_pi_device_id()
        self.assertIsNone(device_id)

    def test_ensure_pi_device_transfers_playback(self):
        """_ensure_pi_device should transfer playback to the Pi device."""
        self.sp._sp.devices.return_value = {
            "devices": [{"id": "d2", "name": "Room Guard"}]
        }
        device_id = self.sp._ensure_pi_device()
        self.assertEqual(device_id, "d2")
        self.sp._sp.transfer_playback.assert_called_once_with("d2", force_play=False)

    def test_ensure_pi_device_returns_none_when_not_found(self):
        """_ensure_pi_device should return None if Pi device is absent."""
        self.sp._sp.devices.return_value = {
            "devices": [{"id": "d1", "name": "Phone"}]
        }
        device_id = self.sp._ensure_pi_device()
        self.assertIsNone(device_id)
        self.sp._sp.transfer_playback.assert_not_called()


class TestJsonCacheHandler(unittest.TestCase):
    """Tests for the custom spotipy cache handler."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "spotify.json")

    def test_get_cached_token_no_file(self):
        handler = _JsonCacheHandler("/nonexistent/path.json")
        result = handler.get_cached_token()
        self.assertIsNone(result)

    def test_get_cached_token_with_tokens(self):
        data = {
            "client_id": "id",
            "client_secret": "secret",
            "access_token": "acc",
            "refresh_token": "ref",
            "expires_at": 9999999999,
        }
        with open(self.config_path, "w") as f:
            json.dump(data, f)

        handler = _JsonCacheHandler(self.config_path)
        token = handler.get_cached_token()
        self.assertIsNotNone(token)
        self.assertEqual(token["access_token"], "acc")
        self.assertEqual(token["refresh_token"], "ref")

    def test_get_cached_token_missing_tokens(self):
        data = {"client_id": "id", "client_secret": "secret"}
        with open(self.config_path, "w") as f:
            json.dump(data, f)

        handler = _JsonCacheHandler(self.config_path)
        token = handler.get_cached_token()
        self.assertIsNone(token)

    def test_save_token_preserves_credentials(self):
        data = {"client_id": "my_id", "client_secret": "my_secret"}
        with open(self.config_path, "w") as f:
            json.dump(data, f)

        handler = _JsonCacheHandler(self.config_path)
        handler.save_token_to_cache({
            "access_token": "new_acc",
            "refresh_token": "new_ref",
            "expires_at": 1234567890,
        })

        with open(self.config_path, "r") as f:
            saved = json.load(f)

        self.assertEqual(saved["client_id"], "my_id")
        self.assertEqual(saved["client_secret"], "my_secret")
        self.assertEqual(saved["access_token"], "new_acc")
        self.assertEqual(saved["refresh_token"], "new_ref")

    def test_save_token_creates_file(self):
        handler = _JsonCacheHandler(self.config_path)
        handler.save_token_to_cache({
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_at": 0,
        })
        self.assertTrue(os.path.exists(self.config_path))


class TestSimplifyTrack(unittest.TestCase):
    """Tests for the track simplification helper."""

    def test_full_track(self):
        track = {
            "uri": "spotify:track:abc",
            "name": "My Song",
            "duration_ms": 240000,
            "artists": [{"name": "Artist A"}, {"name": "Artist B"}],
            "album": {
                "name": "My Album",
                "images": [
                    {"url": "https://large.jpg"},
                    {"url": "https://small.jpg"},
                ],
            },
        }
        result = SpotifyPlayer._simplify_track(track)
        self.assertEqual(result["uri"], "spotify:track:abc")
        self.assertEqual(result["name"], "My Song")
        self.assertEqual(result["artist"], "Artist A, Artist B")
        self.assertEqual(result["album"], "My Album")
        self.assertEqual(result["album_art"], "https://large.jpg")
        self.assertEqual(result["duration_ms"], 240000)

    def test_track_no_album_art(self):
        track = {
            "uri": "spotify:track:xyz",
            "name": "No Art",
            "duration_ms": 120000,
            "artists": [{"name": "Solo"}],
            "album": {"name": "Plain", "images": []},
        }
        result = SpotifyPlayer._simplify_track(track)
        self.assertIsNone(result["album_art"])

    def test_track_missing_fields(self):
        track = {}
        result = SpotifyPlayer._simplify_track(track)
        self.assertEqual(result["uri"], "")
        self.assertEqual(result["name"], "")
        self.assertEqual(result["artist"], "")


if __name__ == "__main__":
    unittest.main()
