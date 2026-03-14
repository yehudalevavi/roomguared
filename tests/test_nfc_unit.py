#!/usr/bin/env python3
"""
Unit tests for the NFC card reader module.

These tests mock the hardware so they can run anywhere (no Raspberry Pi needed).
Run with: python3 -m pytest tests/test_nfc_unit.py -v
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Mock hardware libraries before importing
sys.modules["gpiozero"] = MagicMock()
sys.modules["mfrc522"] = MagicMock()
sys.modules["RPi"] = MagicMock()
sys.modules["RPi.GPIO"] = MagicMock()
sys.modules["spidev"] = MagicMock()

sys.path.insert(0, "src")
from nfc_reader import NFCReader, uid_to_hex, NFC_RST_PIN, DEBOUNCE_SECONDS, POLL_INTERVAL


class TestNFCConfig(unittest.TestCase):
    """Tests for NFC configuration constants."""

    def test_rst_pin_is_25(self):
        self.assertEqual(NFC_RST_PIN, 25)

    def test_debounce_is_positive(self):
        self.assertGreater(DEBOUNCE_SECONDS, 0)

    def test_poll_interval_is_positive(self):
        self.assertGreater(POLL_INTERVAL, 0)

    def test_poll_interval_less_than_one_second(self):
        self.assertLess(POLL_INTERVAL, 1.0)


class TestUidToHex(unittest.TestCase):
    """Tests for the uid_to_hex helper function."""

    def test_single_byte(self):
        self.assertEqual(uid_to_hex([0xFF]), "0xFF")

    def test_four_bytes(self):
        self.assertEqual(uid_to_hex([0x1A, 0x2B, 0x3C, 0x4D]), "0x1A2B3C4D")

    def test_zero_bytes(self):
        self.assertEqual(uid_to_hex([0x00, 0x00, 0x00, 0x00]), "0x00000000")

    def test_empty_list(self):
        self.assertEqual(uid_to_hex([]), "0x")

    def test_leading_zeros_preserved(self):
        self.assertEqual(uid_to_hex([0x01, 0x02]), "0x0102")


class TestNFCReaderInit(unittest.TestCase):
    """Tests for NFCReader initialization."""

    def setUp(self):
        self.config_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump({"cards": [
            {"uid": "0x1A2B3C4D", "action": "toggle_arm", "label": "Test Card"},
            {"uid": "0x5E6F7A8B", "action": "toggle_led", "label": "Blue Fob"},
        ]}, self.config_file)
        self.config_file.close()

    def tearDown(self):
        os.unlink(self.config_file.name)

    def test_loads_config_on_init(self):
        guard = MagicMock()
        nfc = NFCReader(guard, config_path=self.config_file.name)
        self.assertEqual(len(nfc._cards), 2)

    def test_first_card_uid(self):
        guard = MagicMock()
        nfc = NFCReader(guard, config_path=self.config_file.name)
        self.assertEqual(nfc._cards[0]["uid"], "0x1A2B3C4D")

    def test_first_card_action(self):
        guard = MagicMock()
        nfc = NFCReader(guard, config_path=self.config_file.name)
        self.assertEqual(nfc._cards[0]["action"], "toggle_arm")

    def test_first_card_label(self):
        guard = MagicMock()
        nfc = NFCReader(guard, config_path=self.config_file.name)
        self.assertEqual(nfc._cards[0]["label"], "Test Card")

    def test_initial_state(self):
        guard = MagicMock()
        nfc = NFCReader(guard, config_path=self.config_file.name)
        self.assertFalse(nfc._running)
        self.assertIsNone(nfc._reader)
        self.assertIsNone(nfc._thread)
        self.assertIsNone(nfc._last_scan)

    def test_missing_config_file(self):
        guard = MagicMock()
        nfc = NFCReader(guard, config_path="/nonexistent/path.json")
        self.assertEqual(nfc._cards, [])

    def test_invalid_json_config(self):
        bad_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        bad_file.write("not valid json {{{")
        bad_file.close()
        guard = MagicMock()
        nfc = NFCReader(guard, config_path=bad_file.name)
        self.assertEqual(nfc._cards, [])
        os.unlink(bad_file.name)

    def test_empty_cards_config(self):
        empty_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump({"cards": []}, empty_file)
        empty_file.close()
        guard = MagicMock()
        nfc = NFCReader(guard, config_path=empty_file.name)
        self.assertEqual(nfc._cards, [])
        os.unlink(empty_file.name)


class TestNFCReaderRegistration(unittest.TestCase):
    """Tests for card registration and removal."""

    def setUp(self):
        self.config_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump({"cards": []}, self.config_file)
        self.config_file.close()
        self.guard = MagicMock()
        self.nfc = NFCReader(self.guard, config_path=self.config_file.name)

    def tearDown(self):
        os.unlink(self.config_file.name)

    def test_register_new_card(self):
        self.nfc.register_card("0xAABBCCDD", "toggle_arm", "My Card")
        self.assertEqual(len(self.nfc._cards), 1)
        self.assertEqual(self.nfc._cards[0]["uid"], "0xAABBCCDD")

    def test_register_persists_to_file(self):
        self.nfc.register_card("0xAABBCCDD", "toggle_arm", "My Card")
        with open(self.config_file.name) as f:
            data = json.load(f)
        self.assertEqual(len(data["cards"]), 1)
        self.assertEqual(data["cards"][0]["uid"], "0xAABBCCDD")

    def test_register_updates_existing_card(self):
        self.nfc.register_card("0xAABBCCDD", "toggle_arm", "Card v1")
        self.nfc.register_card("0xAABBCCDD", "toggle_led", "Card v2")
        self.assertEqual(len(self.nfc._cards), 1)
        self.assertEqual(self.nfc._cards[0]["action"], "toggle_led")
        self.assertEqual(self.nfc._cards[0]["label"], "Card v2")

    def test_remove_existing_card(self):
        self.nfc.register_card("0xAABBCCDD", "toggle_arm", "Test")
        result = self.nfc.remove_card("0xAABBCCDD")
        self.assertTrue(result)
        self.assertEqual(len(self.nfc._cards), 0)

    def test_remove_nonexistent_card(self):
        result = self.nfc.remove_card("0xDEADBEEF")
        self.assertFalse(result)

    def test_remove_persists_to_file(self):
        self.nfc.register_card("0xAABBCCDD", "toggle_arm", "Test")
        self.nfc.remove_card("0xAABBCCDD")
        with open(self.config_file.name) as f:
            data = json.load(f)
        self.assertEqual(len(data["cards"]), 0)

    def test_get_registered_cards_returns_copy(self):
        self.nfc.register_card("0xAABBCCDD", "toggle_arm", "Test")
        cards = self.nfc.get_registered_cards()
        cards.append({"uid": "0xFAKE", "action": "fake"})
        self.assertEqual(len(self.nfc._cards), 1)

    def test_register_multiple_cards(self):
        self.nfc.register_card("0x11111111", "toggle_arm", "Card 1")
        self.nfc.register_card("0x22222222", "toggle_led", "Card 2")
        self.nfc.register_card("0x33333333", "stop_melody", "Card 3")
        self.assertEqual(len(self.nfc._cards), 3)


class TestNFCReaderDispatch(unittest.TestCase):
    """Tests for action dispatching to RoomGuard."""

    def setUp(self):
        self.config_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump({"cards": [
            {"uid": "0xARM", "action": "toggle_arm", "label": "Arm Card"},
            {"uid": "0xLED", "action": "toggle_led", "label": "LED Card"},
            {"uid": "0xPLAY", "action": "play_melody:Ode to Joy", "label": "Play Card"},
            {"uid": "0xRAND", "action": "play_random", "label": "Random Card"},
            {"uid": "0xSTOP", "action": "stop_melody", "label": "Stop Card"},
        ]}, self.config_file)
        self.config_file.close()
        self.guard = MagicMock()
        self.guard._lock = MagicMock()
        self.guard._buzzer = MagicMock()
        self.nfc = NFCReader(self.guard, config_path=self.config_file.name)

    def tearDown(self):
        os.unlink(self.config_file.name)

    def test_toggle_arm_dispatches(self):
        self.guard.toggle_arm.return_value = True
        self.nfc._dispatch("toggle_arm", "Test")
        self.guard.toggle_arm.assert_called_once()

    def test_toggle_led_dispatches(self):
        self.guard._led_on = False
        self.nfc._dispatch("toggle_led", "Test")
        self.guard.set_led.assert_called_once_with(True)

    def test_toggle_led_off_when_on(self):
        self.guard._led_on = True
        self.nfc._dispatch("toggle_led", "Test")
        self.guard.set_led.assert_called_once_with(False)

    def test_play_melody_dispatches(self):
        self.nfc._dispatch("play_melody:Ode to Joy", "Test")
        self.guard.play_melody_by_name.assert_called_once_with("Ode to Joy")

    def test_play_random_dispatches(self):
        self.guard.play_current_melody.return_value = "Test Melody"
        self.nfc._dispatch("play_random", "Test")
        self.guard.play_current_melody.assert_called_once()

    def test_stop_melody_dispatches(self):
        self.nfc._dispatch("stop_melody", "Test")
        self.guard.stop_melody.assert_called_once()

    def test_unknown_action_no_crash(self):
        self.nfc._dispatch("nonexistent_action", "Test")

    def test_guard_exception_handled(self):
        self.guard.toggle_arm.side_effect = RuntimeError("hardware error")
        self.nfc._dispatch("toggle_arm", "Test")

    def test_dispatch_logs_message(self):
        self.guard.toggle_arm.return_value = True
        self.nfc._dispatch("toggle_arm", "My Card")
        self.guard._log_message.assert_called()


class TestNFCReaderDebounce(unittest.TestCase):
    """Tests for card debounce logic."""

    def setUp(self):
        self.config_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump({"cards": [
            {"uid": "0xABCD1234", "action": "toggle_arm", "label": "Test"},
        ]}, self.config_file)
        self.config_file.close()
        self.guard = MagicMock()
        self.guard._lock = MagicMock()
        self.guard._buzzer = MagicMock()
        self.guard.toggle_arm.return_value = True
        self.nfc = NFCReader(self.guard, config_path=self.config_file.name)

    def tearDown(self):
        os.unlink(self.config_file.name)

    def test_first_tap_dispatches(self):
        self.nfc._handle_card("0xABCD1234")
        self.guard.toggle_arm.assert_called_once()

    def test_immediate_second_tap_debounced(self):
        self.nfc._handle_card("0xABCD1234")
        self.nfc._handle_card("0xABCD1234")
        self.guard.toggle_arm.assert_called_once()

    def test_different_card_not_debounced(self):
        self.nfc._handle_card("0xABCD1234")
        self.nfc._handle_card("0xDIFFERENT")
        # First card triggers toggle_arm, second is unknown (error beep)
        self.guard.toggle_arm.assert_called_once()

    @patch("nfc_reader.time")
    def test_tap_after_debounce_window_dispatches(self, mock_time):
        mock_time.monotonic.side_effect = [0.0, 3.0]
        self.nfc._handle_card("0xABCD1234")
        self.nfc._handle_card("0xABCD1234")
        self.assertEqual(self.guard.toggle_arm.call_count, 2)

    def test_last_scan_updated(self):
        self.nfc._handle_card("0xABCD1234")
        scan = self.nfc.get_last_scan()
        self.assertIsNotNone(scan)
        self.assertEqual(scan["uid"], "0xABCD1234")
        self.assertIn("time", scan)

    def test_last_scan_returns_copy(self):
        self.nfc._handle_card("0xABCD1234")
        scan1 = self.nfc.get_last_scan()
        scan1["uid"] = "MODIFIED"
        scan2 = self.nfc.get_last_scan()
        self.assertEqual(scan2["uid"], "0xABCD1234")


class TestNFCReaderScanMode(unittest.TestCase):
    """Tests for scan-to-register mode."""

    def setUp(self):
        self.config_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump({"cards": [
            {"uid": "0xEXISTING", "action": "toggle_arm", "label": "Existing"},
        ]}, self.config_file)
        self.config_file.close()
        self.guard = MagicMock()
        self.guard._lock = MagicMock()
        self.guard._buzzer = MagicMock()
        self.nfc = NFCReader(self.guard, config_path=self.config_file.name)

    def tearDown(self):
        os.unlink(self.config_file.name)

    def test_scan_captures_uid(self):
        import threading
        def tap_card():
            import time
            time.sleep(0.1)
            self.nfc._handle_card("0xNEWCARD")
        threading.Thread(target=tap_card, daemon=True).start()
        uid = self.nfc.wait_for_scan(timeout=2.0)
        self.assertEqual(uid, "0xNEWCARD")

    def test_scan_returns_none_on_timeout(self):
        uid = self.nfc.wait_for_scan(timeout=0.2)
        self.assertIsNone(uid)

    def test_scan_mode_does_not_dispatch(self):
        import threading
        def tap_card():
            import time
            time.sleep(0.1)
            self.nfc._handle_card("0xEXISTING")
        threading.Thread(target=tap_card, daemon=True).start()
        uid = self.nfc.wait_for_scan(timeout=2.0)
        self.assertEqual(uid, "0xEXISTING")
        # Should NOT have dispatched toggle_arm
        self.guard.toggle_arm.assert_not_called()

    def test_is_scanning_false_by_default(self):
        self.assertFalse(self.nfc.is_scanning)

    def test_dispatch_next_melody(self):
        self.guard.next_melody.return_value = "Ode to Joy"
        self.nfc._dispatch("next_melody", "Test")
        self.guard.next_melody.assert_called_once()

    def test_dispatch_prev_melody(self):
        self.guard.prev_melody.return_value = "Für Elise"
        self.nfc._dispatch("prev_melody", "Test")
        self.guard.prev_melody.assert_called_once()


class TestNFCReaderLifecycle(unittest.TestCase):
    """Tests for start/stop lifecycle."""

    def test_stop_when_not_started(self):
        nfc = NFCReader(MagicMock(), config_path="/nonexistent.json")
        nfc.stop()  # should not raise

    def test_stop_sets_running_false(self):
        nfc = NFCReader(MagicMock(), config_path="/nonexistent.json")
        nfc._running = True
        nfc._reader = MagicMock()
        nfc.stop()
        self.assertFalse(nfc._running)
        self.assertIsNone(nfc._reader)

    def test_double_stop(self):
        nfc = NFCReader(MagicMock(), config_path="/nonexistent.json")
        nfc._running = True
        nfc._reader = MagicMock()
        nfc.stop()
        nfc.stop()  # should not raise


if __name__ == "__main__":
    unittest.main()
