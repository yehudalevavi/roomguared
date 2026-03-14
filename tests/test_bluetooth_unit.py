#!/usr/bin/env python3
"""
Unit tests for the Bluetooth speaker module.

Mocks subprocess calls to bluetoothctl so tests run anywhere.
Run with: python3 -m pytest tests/test_bluetooth_unit.py -v
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, "src")
from bluetooth_speaker import BluetoothSpeaker, _run_bluetoothctl


class TestRunBluetoothctl(unittest.TestCase):
    """Tests for the _run_bluetoothctl helper."""

    @patch("bluetooth_speaker.subprocess.run")
    def test_successful_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="OK\n")
        success, output = _run_bluetoothctl("power", "on")
        self.assertTrue(success)
        self.assertEqual(output, "OK")
        mock_run.assert_called_once_with(
            ["bluetoothctl", "power", "on"],
            capture_output=True, text=True, timeout=10
        )

    @patch("bluetooth_speaker.subprocess.run")
    def test_failed_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="Failed")
        success, output = _run_bluetoothctl("connect", "XX:XX")
        self.assertFalse(success)

    @patch("bluetooth_speaker.subprocess.run", side_effect=FileNotFoundError)
    def test_bluetoothctl_not_found(self, mock_run):
        success, output = _run_bluetoothctl("power", "on")
        self.assertFalse(success)
        self.assertIn("not found", output)

    @patch("bluetooth_speaker.subprocess.run", side_effect=Exception("boom"))
    def test_generic_exception(self, mock_run):
        success, output = _run_bluetoothctl("power", "on")
        self.assertFalse(success)
        self.assertIn("boom", output)


class TestBluetoothSpeakerInit(unittest.TestCase):
    """Tests for initialization."""

    def test_default_state(self):
        bt = BluetoothSpeaker(config_path="/nonexistent/path.json")
        self.assertFalse(bt._connected)
        self.assertFalse(bt._paired)
        self.assertIsNone(bt._device_address)
        self.assertIsNone(bt._device_name)
        self.assertFalse(bt._started)


class TestBluetoothSpeakerLifecycle(unittest.TestCase):
    """Tests for start/stop lifecycle."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "bluetooth.json")
        self.bt = BluetoothSpeaker(config_path=self.config_path)

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_start_powers_on_adapter(self, mock_ctl):
        mock_ctl.return_value = (True, "")
        self.bt.start()
        self.assertTrue(self.bt._started)
        mock_ctl.assert_called_with("power", "on")

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_start_loads_config(self, mock_ctl):
        mock_ctl.return_value = (True, "")
        # Write a config file
        config = {"last_device_address": "AA:BB:CC:DD:EE:FF", "last_device_name": "JBL"}
        with open(self.config_path, "w") as f:
            json.dump(config, f)

        self.bt.start()
        self.assertEqual(self.bt._device_address, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(self.bt._device_name, "JBL")
        self.assertTrue(self.bt._paired)

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_stop(self, mock_ctl):
        mock_ctl.return_value = (True, "")
        self.bt.start()
        self.bt.stop()
        self.assertFalse(self.bt._started)


class TestBluetoothSpeakerScan(unittest.TestCase):
    """Tests for device scanning."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "bluetooth.json")
        self.bt = BluetoothSpeaker(config_path=self.config_path)
        self.bt._started = True

    def test_scan_without_start_raises(self):
        bt = BluetoothSpeaker(config_path=self.config_path)
        with self.assertRaises(RuntimeError):
            bt.scan()

    @patch("bluetooth_speaker.time")
    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_scan_parses_devices(self, mock_ctl, mock_time):
        def ctl_side_effect(*args, **kwargs):
            cmd = args[0] if args else ""
            if cmd == "devices":
                return (True, "Device AA:BB:CC:DD:EE:FF JBL Flip 7\nDevice 11:22:33:44:55:66 AirPods Pro")
            if cmd == "info":
                addr = args[1] if len(args) > 1 else ""
                if "AA:BB" in addr:
                    return (True, "Paired: yes\nConnected: no")
                return (True, "Paired: no\nConnected: no")
            return (True, "")

        mock_ctl.side_effect = ctl_side_effect

        devices = self.bt.scan(timeout=1)
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]["address"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(devices[0]["name"], "JBL Flip 7")
        self.assertTrue(devices[0]["paired"])
        self.assertFalse(devices[0]["connected"])
        self.assertFalse(devices[1]["paired"])

    @patch("bluetooth_speaker.time")
    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_scan_empty_result(self, mock_ctl, mock_time):
        mock_ctl.return_value = (False, "")
        devices = self.bt.scan(timeout=1)
        self.assertEqual(devices, [])


class TestBluetoothSpeakerPairConnect(unittest.TestCase):
    """Tests for pairing and connecting."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "bluetooth.json")
        self.bt = BluetoothSpeaker(config_path=self.config_path)
        self.bt._started = True

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_pair_success(self, mock_ctl):
        def ctl_side_effect(*args, **kwargs):
            cmd = args[0] if args else ""
            if cmd == "pair":
                return (True, "Pairing successful")
            if cmd == "connect":
                return (True, "Connected")
            if cmd == "info":
                return (True, "Name: JBL Flip 7\nPaired: yes\nConnected: yes")
            return (True, "")

        mock_ctl.side_effect = ctl_side_effect

        result = self.bt.pair("AA:BB:CC:DD:EE:FF")
        self.assertTrue(result)
        self.assertTrue(self.bt._connected)
        self.assertEqual(self.bt._device_address, "AA:BB:CC:DD:EE:FF")

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_pair_failure(self, mock_ctl):
        mock_ctl.return_value = (False, "Failed to pair")
        result = self.bt.pair("AA:BB:CC:DD:EE:FF")
        self.assertFalse(result)

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_pair_already_exists_still_connects(self, mock_ctl):
        def ctl_side_effect(*args, **kwargs):
            cmd = args[0] if args else ""
            if cmd == "pair":
                return (False, "Already Exists")
            if cmd == "connect":
                return (True, "Connected")
            if cmd == "info":
                return (True, "Name: JBL Flip 7")
            return (True, "")

        mock_ctl.side_effect = ctl_side_effect
        result = self.bt.pair("AA:BB:CC:DD:EE:FF")
        self.assertTrue(result)

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_connect_success(self, mock_ctl):
        def ctl_side_effect(*args, **kwargs):
            cmd = args[0] if args else ""
            if cmd == "connect":
                return (True, "Connected")
            if cmd == "info":
                return (True, "Name: JBL Flip 7")
            return (True, "")

        mock_ctl.side_effect = ctl_side_effect

        result = self.bt.connect("AA:BB:CC:DD:EE:FF")
        self.assertTrue(result)
        self.assertTrue(self.bt._connected)
        self.assertTrue(self.bt._paired)
        self.assertEqual(self.bt._device_name, "JBL Flip 7")

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_connect_saves_config(self, mock_ctl):
        def ctl_side_effect(*args, **kwargs):
            cmd = args[0] if args else ""
            if cmd == "connect":
                return (True, "Connected")
            if cmd == "info":
                return (True, "Name: JBL Flip 7")
            return (True, "")

        mock_ctl.side_effect = ctl_side_effect
        self.bt.connect("AA:BB:CC:DD:EE:FF")

        with open(self.config_path, "r") as f:
            data = json.load(f)
        self.assertEqual(data["last_device_address"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(data["last_device_name"], "JBL Flip 7")

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_connect_failure(self, mock_ctl):
        mock_ctl.return_value = (False, "Connection failed")
        result = self.bt.connect("AA:BB:CC:DD:EE:FF")
        self.assertFalse(result)
        self.assertFalse(self.bt._connected)

    def test_connect_without_start_raises(self):
        bt = BluetoothSpeaker(config_path=self.config_path)
        with self.assertRaises(RuntimeError):
            bt.connect("AA:BB:CC:DD:EE:FF")


class TestBluetoothSpeakerDisconnectRemove(unittest.TestCase):
    """Tests for disconnect and remove."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "bluetooth.json")
        self.bt = BluetoothSpeaker(config_path=self.config_path)
        self.bt._started = True
        self.bt._connected = True
        self.bt._paired = True
        self.bt._device_address = "AA:BB:CC:DD:EE:FF"
        self.bt._device_name = "JBL Flip 7"

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_disconnect(self, mock_ctl):
        mock_ctl.return_value = (True, "")
        result = self.bt.disconnect()
        self.assertTrue(result)
        self.assertFalse(self.bt._connected)

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_disconnect_no_device(self, mock_ctl):
        self.bt._device_address = None
        result = self.bt.disconnect()
        self.assertFalse(result)

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_remove(self, mock_ctl):
        mock_ctl.return_value = (True, "")
        result = self.bt.remove("AA:BB:CC:DD:EE:FF")
        self.assertTrue(result)
        self.assertFalse(self.bt._connected)
        self.assertFalse(self.bt._paired)
        self.assertIsNone(self.bt._device_address)


class TestBluetoothSpeakerStatus(unittest.TestCase):
    """Tests for get_status."""

    def test_status_disconnected(self):
        bt = BluetoothSpeaker(config_path="/nonexistent/path.json")
        status = bt.get_status()
        self.assertFalse(status["connected"])
        self.assertFalse(status["paired"])
        self.assertIsNone(status["device_name"])
        self.assertIsNone(status["device_address"])

    def test_status_connected(self):
        bt = BluetoothSpeaker(config_path="/nonexistent/path.json")
        bt._connected = True
        bt._paired = True
        bt._device_address = "AA:BB:CC:DD:EE:FF"
        bt._device_name = "JBL Flip 7"
        status = bt.get_status()
        self.assertTrue(status["connected"])
        self.assertTrue(status["paired"])
        self.assertEqual(status["device_name"], "JBL Flip 7")
        self.assertEqual(status["device_address"], "AA:BB:CC:DD:EE:FF")


class TestBluetoothSpeakerAutoConnect(unittest.TestCase):
    """Tests for auto_connect."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "bluetooth.json")
        self.bt = BluetoothSpeaker(config_path=self.config_path)
        self.bt._started = True

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_auto_connect_with_saved_device(self, mock_ctl):
        def ctl_side_effect(*args, **kwargs):
            cmd = args[0] if args else ""
            if cmd == "connect":
                return (True, "Connected")
            if cmd == "info":
                return (True, "Name: JBL Flip 7")
            return (True, "")

        mock_ctl.side_effect = ctl_side_effect
        self.bt._device_address = "AA:BB:CC:DD:EE:FF"

        result = self.bt.auto_connect()
        self.assertTrue(result)
        self.assertTrue(self.bt._connected)

    @patch("bluetooth_speaker._run_bluetoothctl")
    def test_auto_connect_no_saved_device(self, mock_ctl):
        result = self.bt.auto_connect()
        self.assertFalse(result)

    def test_auto_connect_without_start_raises(self):
        bt = BluetoothSpeaker(config_path=self.config_path)
        with self.assertRaises(RuntimeError):
            bt.auto_connect()


class TestBluetoothSpeakerConfig(unittest.TestCase):
    """Tests for config persistence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "bluetooth.json")

    def test_load_missing_config(self):
        bt = BluetoothSpeaker(config_path="/nonexistent/path.json")
        bt._load_config()
        self.assertIsNone(bt._device_address)

    def test_load_valid_config(self):
        config = {"last_device_address": "AA:BB:CC:DD:EE:FF", "last_device_name": "JBL"}
        with open(self.config_path, "w") as f:
            json.dump(config, f)

        bt = BluetoothSpeaker(config_path=self.config_path)
        bt._load_config()
        self.assertEqual(bt._device_address, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(bt._device_name, "JBL")
        self.assertTrue(bt._paired)

    def test_load_corrupt_config(self):
        with open(self.config_path, "w") as f:
            f.write("not valid json{{{")

        bt = BluetoothSpeaker(config_path=self.config_path)
        bt._load_config()
        self.assertIsNone(bt._device_address)

    def test_save_config(self):
        bt = BluetoothSpeaker(config_path=self.config_path)
        bt._device_address = "11:22:33:44:55:66"
        bt._device_name = "Test Speaker"
        bt._save_config()

        with open(self.config_path, "r") as f:
            data = json.load(f)
        self.assertEqual(data["last_device_address"], "11:22:33:44:55:66")
        self.assertEqual(data["last_device_name"], "Test Speaker")


if __name__ == "__main__":
    unittest.main()
