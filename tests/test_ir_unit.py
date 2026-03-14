#!/usr/bin/env python3
"""
Unit tests for the IR remote control module.

These tests mock the hardware so they can run anywhere (no Raspberry Pi needed).
Run with: python3 -m pytest tests/test_ir_unit.py -v
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock hardware libraries before importing
sys.modules["gpiozero"] = MagicMock()

sys.path.insert(0, "src")
from ir_remote import IRRemote, ELEGOO_SCANCODE_MAP, IR_PIN, DEBOUNCE_MS


class TestIRConfig(unittest.TestCase):
    """Tests for IR remote configuration constants."""

    def test_ir_pin_is_18(self):
        self.assertEqual(IR_PIN, 18)

    def test_elegoo_map_has_four_entries(self):
        self.assertEqual(len(ELEGOO_SCANCODE_MAP), 10)

    def test_elegoo_map_has_prev_melody(self):
        self.assertIn("prev_melody", ELEGOO_SCANCODE_MAP.values())

    def test_elegoo_map_has_play_pause(self):
        self.assertIn("play_pause", ELEGOO_SCANCODE_MAP.values())

    def test_elegoo_map_has_next_melody(self):
        self.assertIn("next_melody", ELEGOO_SCANCODE_MAP.values())

    def test_elegoo_map_has_toggle_arm(self):
        self.assertIn("toggle_arm", ELEGOO_SCANCODE_MAP.values())

    def test_elegoo_scancodes_are_integers(self):
        for code in ELEGOO_SCANCODE_MAP:
            self.assertIsInstance(code, int)


class TestIRRemoteInit(unittest.TestCase):
    """Tests for IRRemote initialization."""

    def test_default_scancode_map(self):
        guard = MagicMock()
        ir = IRRemote(guard)
        self.assertEqual(ir._scancode_map, ELEGOO_SCANCODE_MAP)

    def test_custom_scancode_map(self):
        guard = MagicMock()
        custom = {0x01: "toggle_arm", 0x02: "play_pause"}
        ir = IRRemote(guard, scancode_map=custom)
        self.assertEqual(ir._scancode_map, custom)

    def test_does_not_mutate_default_map(self):
        guard = MagicMock()
        ir = IRRemote(guard)
        ir._scancode_map[0xFF] = "test"
        self.assertNotIn(0xFF, ELEGOO_SCANCODE_MAP)

    def test_initial_state(self):
        guard = MagicMock()
        ir = IRRemote(guard)
        self.assertFalse(ir._running)
        self.assertIsNone(ir._device)
        self.assertIsNone(ir._thread)

    def test_debounce_ms_is_positive(self):
        self.assertGreater(DEBOUNCE_MS, 0)


class TestIRRemoteDispatch(unittest.TestCase):
    """Tests for action dispatching to RoomGuard."""

    def setUp(self):
        self.guard = MagicMock()
        self.ir = IRRemote(self.guard)

    def test_prev_melody_calls_guard(self):
        self.guard.prev_melody.return_value = "Ode to Joy"
        self.ir._dispatch("prev_melody")
        self.guard.prev_melody.assert_called_once()

    def test_next_melody_calls_guard(self):
        self.guard.next_melody.return_value = "Für Elise"
        self.ir._dispatch("next_melody")
        self.guard.next_melody.assert_called_once()

    def test_play_pause_plays_when_not_playing(self):
        self.guard._playing = False
        self.guard.play_current_melody.return_value = "Jingle Bells"
        self.ir._dispatch("play_pause")
        self.guard.play_current_melody.assert_called_once()
        self.guard.stop_melody.assert_not_called()

    def test_play_pause_stops_when_playing(self):
        self.guard._playing = True
        self.ir._dispatch("play_pause")
        self.guard.stop_melody.assert_called_once()
        self.guard.play_current_melody.assert_not_called()

    def test_toggle_arm_calls_guard(self):
        self.guard.toggle_arm.return_value = True
        self.ir._dispatch("toggle_arm")
        self.guard.toggle_arm.assert_called_once()

    def test_unknown_action_no_error(self):
        # Should not raise for unmapped actions
        self.ir._dispatch("nonexistent_action")

    def test_guard_exception_handled_gracefully(self):
        self.guard.next_melody.side_effect = RuntimeError("hardware error")
        # Should not propagate
        self.ir._dispatch("next_melody")

    def test_toggle_arm_exception_handled(self):
        self.guard.toggle_arm.side_effect = RuntimeError("test")
        self.ir._dispatch("toggle_arm")

    def test_spotify_random_calls_guard(self):
        self.guard.play_random_song.return_value = {"name": "Test Song"}
        self.ir._dispatch("spotify_random")
        self.guard.play_random_song.assert_called_once()

    def test_spotify_random_handles_none(self):
        self.guard.play_random_song.return_value = None
        self.ir._dispatch("spotify_random")  # should not raise

    def test_spotify_pause_when_playing(self):
        self.guard._spotify = MagicMock()
        self.guard._spotify.get_current_playback.return_value = {"is_playing": True}
        self.ir._dispatch("spotify_pause")
        self.guard.spotify_pause.assert_called_once()
        self.guard.spotify_resume.assert_not_called()

    def test_spotify_pause_when_paused(self):
        self.guard._spotify = MagicMock()
        self.guard._spotify.get_current_playback.return_value = {"is_playing": False}
        self.ir._dispatch("spotify_pause")
        self.guard.spotify_resume.assert_called_once()

    def test_spotify_next(self):
        self.ir._dispatch("spotify_next")
        self.guard.spotify_next.assert_called_once()

    def test_spotify_prev(self):
        self.ir._dispatch("spotify_prev")
        self.guard.spotify_prev.assert_called_once()

    def test_volume_up(self):
        self.guard._spotify = MagicMock()
        self.guard._spotify.get_current_playback.return_value = {"volume_percent": 50}
        self.ir._dispatch("volume_up")
        self.guard.spotify_volume.assert_called_once_with(60)

    def test_volume_down(self):
        self.guard._spotify = MagicMock()
        self.guard._spotify.get_current_playback.return_value = {"volume_percent": 50}
        self.ir._dispatch("volume_down")
        self.guard.spotify_volume.assert_called_once_with(40)

    def test_volume_up_caps_at_100(self):
        self.guard._spotify = MagicMock()
        self.guard._spotify.get_current_playback.return_value = {"volume_percent": 95}
        self.ir._dispatch("volume_up")
        self.guard.spotify_volume.assert_called_once_with(100)


class TestIRRemoteLifecycle(unittest.TestCase):
    """Tests for start/stop lifecycle."""

    def test_stop_when_not_started(self):
        ir = IRRemote(MagicMock())
        ir.stop()  # should not raise

    def test_stop_sets_running_false(self):
        ir = IRRemote(MagicMock())
        ir._running = True
        ir._device = MagicMock()
        ir.stop()
        self.assertFalse(ir._running)
        self.assertIsNone(ir._device)

    def test_stop_closes_device(self):
        ir = IRRemote(MagicMock())
        mock_dev = MagicMock()
        ir._device = mock_dev
        ir._running = True
        ir.stop()
        mock_dev.close.assert_called_once()

    def test_stop_handles_close_exception(self):
        ir = IRRemote(MagicMock())
        mock_dev = MagicMock()
        mock_dev.close.side_effect = OSError("already closed")
        ir._device = mock_dev
        ir._running = True
        ir.stop()  # should not raise
        self.assertIsNone(ir._device)

    @patch("ir_remote.IRRemote._find_ir_device", return_value=None)
    def test_start_raises_when_no_device(self, _):
        ir = IRRemote(MagicMock())
        with self.assertRaises(RuntimeError) as ctx:
            ir.start()
        self.assertIn("IR receiver not found", str(ctx.exception))

    @patch("ir_remote.IRRemote._find_ir_device")
    def test_start_sets_running_and_starts_thread(self, mock_find):
        mock_find.return_value = MagicMock()
        ir = IRRemote(MagicMock())
        ir.start()
        self.assertTrue(ir._running)
        self.assertIsNotNone(ir._thread)
        self.assertTrue(ir._thread.daemon)
        ir.stop()

    def test_double_stop(self):
        ir = IRRemote(MagicMock())
        ir._device = MagicMock()
        ir._running = True
        ir.stop()
        ir.stop()  # should not raise


if __name__ == "__main__":
    unittest.main()
