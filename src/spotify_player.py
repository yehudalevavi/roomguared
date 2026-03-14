#!/usr/bin/env python3
"""
Spotify player module for Room Guard.

Wraps the spotipy library to provide OAuth2 authentication,
liked-songs playback, and full transport controls via the
Spotify Web API. Audio is rendered by spotifyd (a separate
Spotify Connect daemon running on the Pi).

The module follows the project's start/stop lifecycle pattern.
Tokens are persisted to config/spotify.json for auto-refresh.

Dependencies (Python):
    pip install spotipy>=2.23

Dependencies (system):
    spotifyd must be running as a systemd service.

Setup:
    1. Create a Spotify Developer App at https://developer.spotify.com/dashboard
    2. Set redirect URI to http://127.0.0.1:5000/api/spotify/callback
    3. Enter client_id and client_secret via the web dashboard or config file
"""

import json
import os
import random
import threading

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "spotify.json"
)

SCOPES = "user-library-read user-modify-playback-state user-read-playback-state user-read-currently-playing"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:5000/api/spotify/callback"
SPOTIFYD_DEVICE_NAME = "Room Guard"


class SpotifyPlayer:
    """
    Spotify Web API controller using spotipy.

    Handles OAuth2 authentication, liked-songs access, and
    playback control. Audio output is handled by spotifyd.
    Call start() before use, stop() to clean up.
    """

    def __init__(self, config_path=None):
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._sp = None  # spotipy.Spotify client
        self._auth_manager = None
        self._config = {}
        self._lock = threading.Lock()
        self._started = False
        self._liked_songs_cache = []
        self._liked_songs_total = 0

    def start(self) -> None:
        """Initialize spotipy client from saved tokens (if available)."""
        self._started = True
        self._load_config()

        if self._config.get("client_id") and self._config.get("client_secret"):
            self._init_client()

        print("[Spotify] Started" + (" (authenticated)" if self.is_authenticated() else " (not authenticated)"))

    def stop(self) -> None:
        """Clean up."""
        self._sp = None
        self._auth_manager = None
        self._started = False
        print("[Spotify] Stopped")

    def is_authenticated(self) -> bool:
        """Check if we have a valid (or refreshable) Spotify session."""
        if self._auth_manager is None:
            return False
        try:
            token_info = self._auth_manager.get_cached_token()
            return token_info is not None
        except Exception:
            return False

    def is_configured(self) -> bool:
        """Check if client credentials are set."""
        return bool(self._config.get("client_id") and self._config.get("client_secret"))

    def set_credentials(self, client_id: str, client_secret: str) -> None:
        """Save Spotify app credentials and reinitialize."""
        self._config["client_id"] = client_id
        self._config["client_secret"] = client_secret
        self._save_config()
        if self._started:
            self._init_client()

    def get_auth_url(self) -> str | None:
        """Generate the Spotify OAuth2 authorization URL.

        Returns the URL to redirect the user to, or None if not configured.
        """
        if not self._started:
            raise RuntimeError("SpotifyPlayer not started. Call start() first.")
        if self._auth_manager is None:
            return None
        return self._auth_manager.get_authorize_url()

    def handle_auth_callback(self, code: str) -> bool:
        """Exchange an OAuth2 authorization code for access+refresh tokens.

        Args:
            code: The authorization code from the Spotify callback.

        Returns:
            True if tokens were obtained successfully.
        """
        if not self._started:
            raise RuntimeError("SpotifyPlayer not started. Call start() first.")
        if self._auth_manager is None:
            return False

        try:
            token_info = self._auth_manager.get_access_token(code, as_dict=True)
            if token_info:
                self._save_tokens(token_info)
                self._init_client()
                print("[Spotify] Authentication successful")
                return True
        except Exception as e:
            print(f"[Spotify] Auth callback failed: {e}")
        return False

    def handle_auth_url(self, url: str) -> bool:
        """Extract the authorization code from a pasted callback URL.

        For headless setups where the redirect goes to localhost on
        the user's browser (not the Pi), the user can copy the full
        URL from the address bar and paste it here.

        Args:
            url: The full callback URL, e.g.
                 http://localhost:5000/api/spotify/callback?code=AQD...

        Returns:
            True if tokens were obtained successfully.
        """
        from urllib.parse import urlparse, parse_qs
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            if not code:
                print("[Spotify] No code found in pasted URL")
                return False
            return self.handle_auth_callback(code)
        except Exception as e:
            print(f"[Spotify] Failed to parse auth URL: {e}")
            return False

    def get_liked_songs(self, limit=50, offset=0) -> list[dict]:
        """Fetch user's liked songs from Spotify.

        Returns a list of simplified track dicts:
        [{uri, name, artist, album, duration_ms, album_art}]
        """
        self._ensure_client()
        try:
            results = self._sp.current_user_saved_tracks(limit=limit, offset=offset)
            tracks = []
            for item in results.get("items", []):
                track = item["track"]
                tracks.append(self._simplify_track(track))
            self._liked_songs_total = results.get("total", 0)
            return tracks
        except Exception as e:
            print(f"[Spotify] Failed to fetch liked songs: {e}")
            return []

    def get_liked_songs_count(self) -> int:
        """Get total number of liked songs (fetches first page if unknown)."""
        self._ensure_client()
        try:
            results = self._sp.current_user_saved_tracks(limit=1)
            self._liked_songs_total = results.get("total", 0)
            return self._liked_songs_total
        except Exception as e:
            print(f"[Spotify] Failed to get liked songs count: {e}")
            return 0

    def play_random_liked_song(self) -> dict | None:
        """Pick a random song from liked songs and start playback.

        Returns simplified track info dict, or None on failure.
        """
        self._ensure_client()
        try:
            # Get total count
            total = self.get_liked_songs_count()
            if total == 0:
                print("[Spotify] No liked songs found")
                return None

            # Pick a random offset
            random_offset = random.randint(0, max(0, total - 1))
            results = self._sp.current_user_saved_tracks(limit=1, offset=random_offset)
            items = results.get("items", [])
            if not items:
                return None

            track = items[0]["track"]
            uri = track["uri"]

            # Start playback on the Pi device
            device_id = self._ensure_pi_device()
            self._sp.start_playback(device_id=device_id, uris=[uri])

            track_info = self._simplify_track(track)
            print(f"[Spotify] Playing: {track_info['name']} — {track_info['artist']}")
            return track_info

        except Exception as e:
            print(f"[Spotify] Failed to play random song: {e}")
            return None

    def play_track(self, uri: str) -> bool:
        """Play a specific Spotify track URI."""
        self._ensure_client()
        try:
            device_id = self._ensure_pi_device()
            self._sp.start_playback(device_id=device_id, uris=[uri])
            return True
        except Exception as e:
            print(f"[Spotify] Failed to play track: {e}")
            return False

    def pause(self) -> bool:
        """Pause playback."""
        self._ensure_client()
        try:
            self._sp.pause_playback()
            return True
        except Exception as e:
            print(f"[Spotify] Failed to pause: {e}")
            return False

    def resume(self) -> bool:
        """Resume playback."""
        self._ensure_client()
        try:
            device_id = self._ensure_pi_device()
            self._sp.start_playback(device_id=device_id)
            return True
        except Exception as e:
            print(f"[Spotify] Failed to resume: {e}")
            return False

    def next_track(self) -> bool:
        """Skip to next track."""
        self._ensure_client()
        try:
            self._sp.next_track()
            return True
        except Exception as e:
            print(f"[Spotify] Failed to skip next: {e}")
            return False

    def prev_track(self) -> bool:
        """Skip to previous track."""
        self._ensure_client()
        try:
            self._sp.previous_track()
            return True
        except Exception as e:
            print(f"[Spotify] Failed to skip previous: {e}")
            return False

    def set_volume(self, percent: int) -> bool:
        """Set playback volume (0-100)."""
        self._ensure_client()
        percent = max(0, min(100, percent))
        try:
            self._sp.volume(percent)
            return True
        except Exception as e:
            print(f"[Spotify] Failed to set volume: {e}")
            return False

    def get_current_playback(self) -> dict | None:
        """Get current playback state.

        Returns dict with: track (simplified), is_playing, progress_ms,
        duration_ms, device_name, volume_percent. Or None if nothing playing.
        """
        self._ensure_client()
        try:
            playback = self._sp.current_playback()
            if not playback or not playback.get("item"):
                return None

            track = playback["item"]
            device = playback.get("device", {})
            return {
                "track": self._simplify_track(track),
                "is_playing": playback.get("is_playing", False),
                "progress_ms": playback.get("progress_ms", 0),
                "duration_ms": track.get("duration_ms", 0),
                "device_name": device.get("name", ""),
                "volume_percent": device.get("volume_percent", 0),
            }
        except Exception as e:
            print(f"[Spotify] Failed to get playback: {e}")
            return None

    def get_devices(self) -> list[dict]:
        """List available Spotify Connect devices."""
        self._ensure_client()
        try:
            result = self._sp.devices()
            return [
                {
                    "id": d["id"],
                    "name": d["name"],
                    "type": d["type"],
                    "is_active": d["is_active"],
                    "volume_percent": d.get("volume_percent"),
                }
                for d in result.get("devices", [])
            ]
        except Exception as e:
            print(f"[Spotify] Failed to list devices: {e}")
            return []

    def transfer_playback(self, device_id: str) -> bool:
        """Transfer playback to a specific Spotify Connect device."""
        self._ensure_client()
        try:
            self._sp.transfer_playback(device_id, force_play=True)
            return True
        except Exception as e:
            print(f"[Spotify] Failed to transfer playback: {e}")
            return False

    def _ensure_client(self):
        """Raise if not started or not authenticated."""
        if not self._started:
            raise RuntimeError("SpotifyPlayer not started. Call start() first.")
        if self._sp is None:
            raise RuntimeError("Spotify not authenticated. Complete OAuth setup first.")

    def _init_client(self) -> None:
        """(Re)initialize the spotipy client with current config."""
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth

            redirect_uri = self._config.get("redirect_uri", DEFAULT_REDIRECT_URI)

            self._auth_manager = SpotifyOAuth(
                client_id=self._config["client_id"],
                client_secret=self._config["client_secret"],
                redirect_uri=redirect_uri,
                scope=SCOPES,
                cache_handler=_JsonCacheHandler(self._config_path),
                open_browser=False,
            )

            # Check if we have valid tokens
            token_info = self._auth_manager.get_cached_token()
            if token_info:
                self._sp = spotipy.Spotify(auth_manager=self._auth_manager)
            else:
                self._sp = None

        except ImportError:
            print("[Spotify] spotipy not installed — pip install spotipy")
            self._auth_manager = None
            self._sp = None
        except Exception as e:
            print(f"[Spotify] Client init failed: {e}")
            self._sp = None

    def _get_pi_device_id(self) -> str | None:
        """Find the Room Guard (raspotify) device in Spotify Connect list.

        Returns the device ID only if it matches SPOTIFYD_DEVICE_NAME.
        Never falls back to other devices — we only want to play on the Pi.
        """
        try:
            result = self._sp.devices()
            for device in result.get("devices", []):
                name = device.get("name", "").lower()
                if SPOTIFYD_DEVICE_NAME.lower() in name:
                    return device["id"]
        except Exception:
            pass
        return None

    def _ensure_pi_device(self) -> str | None:
        """Get the Pi device ID and transfer playback to it.

        This forces Spotify to move the active context to the Pi
        so that play commands don't end up on the desktop or phone.
        Returns the device ID, or None if the Pi device is not found.
        """
        device_id = self._get_pi_device_id()
        if not device_id:
            print("[Spotify] WARNING: Room Guard device not found in Spotify Connect")
            return None
        try:
            self._sp.transfer_playback(device_id, force_play=False)
        except Exception:
            # Transfer may fail if nothing is playing yet — that's OK,
            # start_playback with device_id will still target it.
            pass
        return device_id

    @staticmethod
    def _simplify_track(track: dict) -> dict:
        """Extract the useful fields from a Spotify track object."""
        artists = track.get("artists", [])
        artist_name = ", ".join(a.get("name", "") for a in artists)
        album = track.get("album", {})
        images = album.get("images", [])
        album_art = images[0]["url"] if images else None
        return {
            "uri": track.get("uri", ""),
            "name": track.get("name", ""),
            "artist": artist_name,
            "album": album.get("name", ""),
            "duration_ms": track.get("duration_ms", 0),
            "album_art": album_art,
        }

    def _load_config(self) -> None:
        """Load Spotify config (credentials + tokens) from JSON file."""
        try:
            with open(self._config_path, "r") as f:
                self._config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._config = {}

    def _save_config(self) -> None:
        """Persist current config to JSON file."""
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, "w") as f:
                json.dump(self._config, f, indent=2)
        except OSError as e:
            print(f"[Spotify] WARNING: Could not save config: {e}")

    def _save_tokens(self, token_info: dict) -> None:
        """Merge token info into config and persist."""
        self._config["access_token"] = token_info.get("access_token")
        self._config["refresh_token"] = token_info.get("refresh_token")
        self._config["expires_at"] = token_info.get("expires_at")
        self._config["token_type"] = token_info.get("token_type")
        self._config["scope"] = token_info.get("scope")
        self._save_config()


try:
    from spotipy.cache_handler import CacheHandler as _BaseCacheHandler
except ImportError:
    _BaseCacheHandler = object


class _JsonCacheHandler(_BaseCacheHandler):
    """Custom spotipy cache handler that stores tokens in our config JSON.

    Spotipy's SpotifyOAuth needs a CacheHandler to read/write tokens.
    This handler merges tokens into the existing config/spotify.json
    instead of creating a separate .cache file.

    Inherits from spotipy's CacheHandler to satisfy the isinstance
    check in SpotifyOAuth. Falls back to object if spotipy is not installed.
    """

    def __init__(self, config_path):
        self._config_path = config_path

    def get_cached_token(self):
        try:
            with open(self._config_path, "r") as f:
                data = json.load(f)
            if data.get("access_token") and data.get("refresh_token"):
                return {
                    "access_token": data["access_token"],
                    "refresh_token": data["refresh_token"],
                    "expires_at": data.get("expires_at", 0),
                    "token_type": data.get("token_type", "Bearer"),
                    "scope": data.get("scope", ""),
                }
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
        return None

    def save_token_to_cache(self, token_info):
        try:
            # Load existing config to preserve credentials
            try:
                with open(self._config_path, "r") as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                data = {}

            data["access_token"] = token_info.get("access_token")
            data["refresh_token"] = token_info.get("refresh_token")
            data["expires_at"] = token_info.get("expires_at")
            data["token_type"] = token_info.get("token_type")
            data["scope"] = token_info.get("scope")

            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            print(f"[Spotify] WARNING: Could not save tokens: {e}")
