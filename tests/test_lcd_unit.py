#!/usr/bin/env python3
"""
Unit tests for the LCD1602 display module.

These tests mock the hardware so they can run anywhere (no Raspberry Pi needed).
Run with: python3 -m pytest tests/test_lcd_unit.py -v
"""

import sys
import unittest
from unittest.mock import MagicMock, patch, call

# Mock hardware libraries before importing our module
sys.modules["RPLCD"] = MagicMock()
sys.modules["RPLCD.gpio"] = MagicMock()
sys.modules["RPi"] = MagicMock()
sys.modules["RPi.GPIO"] = MagicMock()

sys.path.insert(0, "src")
from lcd_display import (
    LCDDisplay,
    LCD_RS, LCD_E, LCD_D4, LCD_D5, LCD_D6, LCD_D7,
    LCD_COLS, LCD_ROWS,
)


class TestLCDDisplayInit(unittest.TestCase):
    """Tests for LCD initialization and configuration."""

    def test_default_pins(self):
        lcd = LCDDisplay()
        self.assertEqual(lcd.rs, LCD_RS)
        self.assertEqual(lcd.e, LCD_E)
        self.assertEqual(lcd.data_pins, [LCD_D4, LCD_D5, LCD_D6, LCD_D7])

    def test_default_pin_values(self):
        lcd = LCDDisplay()
        self.assertEqual(lcd.rs, 26)
        self.assertEqual(lcd.e, 19)
        self.assertEqual(lcd.data_pins, [13, 6, 5, 11])

    def test_custom_pins(self):
        lcd = LCDDisplay(rs=1, e=2, d4=3, d5=4, d6=5, d7=6)
        self.assertEqual(lcd.rs, 1)
        self.assertEqual(lcd.e, 2)
        self.assertEqual(lcd.data_pins, [3, 4, 5, 6])

    def test_default_dimensions(self):
        lcd = LCDDisplay()
        self.assertEqual(lcd.cols, 16)
        self.assertEqual(lcd.rows, 2)

    def test_custom_dimensions(self):
        lcd = LCDDisplay(cols=20, rows=4)
        self.assertEqual(lcd.cols, 20)
        self.assertEqual(lcd.rows, 4)

    def test_initial_lines_empty(self):
        lcd = LCDDisplay()
        self.assertEqual(lcd.line1, "")
        self.assertEqual(lcd.line2, "")


class TestLCDDisplayLifecycle(unittest.TestCase):
    """Tests for start/stop lifecycle."""

    def test_start_creates_char_lcd(self):
        lcd = LCDDisplay()
        mock_char_lcd_cls = MagicMock()
        sys.modules["RPLCD.gpio"].CharLCD = mock_char_lcd_cls

        lcd.start()

        mock_char_lcd_cls.assert_called_once()
        call_kwargs = mock_char_lcd_cls.call_args[1]
        self.assertEqual(call_kwargs["cols"], 16)
        self.assertEqual(call_kwargs["rows"], 2)
        self.assertEqual(call_kwargs["pin_rs"], 26)
        self.assertEqual(call_kwargs["pin_e"], 19)
        self.assertEqual(call_kwargs["pins_data"], [13, 6, 5, 11])
        self.assertTrue(call_kwargs["compat_mode"])

    def test_start_clears_display(self):
        lcd = LCDDisplay()
        mock_device = MagicMock()
        sys.modules["RPLCD.gpio"].CharLCD.return_value = mock_device

        lcd.start()

        mock_device.clear.assert_called_once()

    def test_stop_clears_and_closes(self):
        lcd = LCDDisplay()
        mock_device = MagicMock()
        lcd._lcd = mock_device

        lcd.stop()

        mock_device.clear.assert_called_once()
        mock_device.close.assert_called_once_with(clear=True)
        self.assertIsNone(lcd._lcd)

    def test_stop_resets_line_cache(self):
        lcd = LCDDisplay()
        mock_device = MagicMock()
        lcd._lcd = mock_device
        lcd._line1 = "some text       "
        lcd._line2 = "other text      "

        lcd.stop()

        self.assertEqual(lcd._line1, "")
        self.assertEqual(lcd._line2, "")

    def test_stop_when_not_started(self):
        lcd = LCDDisplay()
        lcd.stop()  # should not raise

    def test_double_stop(self):
        lcd = LCDDisplay()
        mock_device = MagicMock()
        lcd._lcd = mock_device

        lcd.stop()
        lcd.stop()  # second stop should not raise


class TestLCDWrite(unittest.TestCase):
    """Tests for writing text to the display."""

    def setUp(self):
        self.lcd = LCDDisplay()
        self.mock_device = MagicMock()
        self.lcd._lcd = self.mock_device

    def test_write_without_start_raises(self):
        lcd = LCDDisplay()
        with self.assertRaises(RuntimeError):
            lcd.write("Hello")

    def test_write_both_lines(self):
        self.lcd.write("Line One", "Line Two")

        # Should set cursor for line 1 and write
        calls = self.mock_device.mock_calls
        self.assertIn(call.write_string("Line One        "), calls)
        self.assertIn(call.write_string("Line Two        "), calls)

    def test_write_pads_short_text(self):
        self.lcd.write("Hi", "")

        calls = self.mock_device.mock_calls
        self.assertIn(call.write_string("Hi              "), calls)
        self.assertIn(call.write_string("                "), calls)

    def test_write_truncates_long_text(self):
        self.lcd.write("This text is way too long", "Also very long text here")

        calls = self.mock_device.mock_calls
        self.assertIn(call.write_string("This text is way"), calls)
        self.assertIn(call.write_string("Also very long t"), calls)

    def test_write_exactly_16_chars(self):
        self.lcd.write("1234567890123456", "ABCDEFGHIJKLMNOP")

        calls = self.mock_device.mock_calls
        self.assertIn(call.write_string("1234567890123456"), calls)
        self.assertIn(call.write_string("ABCDEFGHIJKLMNOP"), calls)

    def test_write_updates_line_properties(self):
        self.lcd.write("Hello", "World")

        self.assertEqual(self.lcd.line1, "Hello")
        self.assertEqual(self.lcd.line2, "World")

    def test_write_only_line1(self):
        self.lcd.write("Only Line 1")

        self.assertEqual(self.lcd.line1, "Only Line 1")
        self.assertEqual(self.lcd.line2, "")

    def test_write_sets_cursor_positions(self):
        self.lcd.write("A", "B")

        # cursor_pos should be set to (0,0) then (1,0)
        cursor_sets = [
            c[1] for c in self.mock_device.mock_calls
            if "cursor_pos" in str(c)
        ]
        # Alternatively, check __setattr__ calls for cursor_pos
        self.assertEqual(self.mock_device.cursor_pos, (1, 0))

    def test_write_skips_unchanged_lines(self):
        self.lcd.write("Static", "Dynamic 1")
        self.mock_device.reset_mock()

        self.lcd.write("Static", "Dynamic 2")

        # Line 1 unchanged — should NOT write it again
        write_calls = [
            c for c in self.mock_device.mock_calls
            if c[0] == "write_string"
        ]
        self.assertEqual(len(write_calls), 1)
        self.assertIn("Dynamic 2", write_calls[0][1][0])

    def test_write_empty_string_clears_line(self):
        self.lcd.write("Some text", "Other text")
        self.mock_device.reset_mock()

        self.lcd.write("", "")

        # Both lines should be written with spaces
        write_calls = [
            c for c in self.mock_device.mock_calls
            if c[0] == "write_string"
        ]
        self.assertEqual(len(write_calls), 2)


class TestLCDClear(unittest.TestCase):
    """Tests for clearing the display."""

    def test_clear_without_start_raises(self):
        lcd = LCDDisplay()
        with self.assertRaises(RuntimeError):
            lcd.clear()

    def test_clear_calls_lcd_clear(self):
        lcd = LCDDisplay()
        mock_device = MagicMock()
        lcd._lcd = mock_device

        lcd.clear()

        mock_device.clear.assert_called_once()

    def test_clear_resets_line_cache(self):
        lcd = LCDDisplay()
        mock_device = MagicMock()
        lcd._lcd = mock_device
        lcd._line1 = "old text        "
        lcd._line2 = "old text        "

        lcd.clear()

        self.assertEqual(lcd._line1, "")
        self.assertEqual(lcd._line2, "")


class TestLCDPad(unittest.TestCase):
    """Tests for the _pad helper method."""

    def setUp(self):
        self.lcd = LCDDisplay()

    def test_pad_short_text(self):
        result = self.lcd._pad("Hi")
        self.assertEqual(result, "Hi              ")
        self.assertEqual(len(result), 16)

    def test_pad_empty_string(self):
        result = self.lcd._pad("")
        self.assertEqual(result, "                ")
        self.assertEqual(len(result), 16)

    def test_pad_exact_length(self):
        result = self.lcd._pad("1234567890123456")
        self.assertEqual(result, "1234567890123456")
        self.assertEqual(len(result), 16)

    def test_pad_truncates_long_text(self):
        result = self.lcd._pad("This is a very long string that exceeds 16")
        self.assertEqual(result, "This is a very l")
        self.assertEqual(len(result), 16)

    def test_pad_custom_width(self):
        lcd = LCDDisplay(cols=20)
        result = lcd._pad("Hello")
        self.assertEqual(result, "Hello               ")
        self.assertEqual(len(result), 20)


class TestLCDLineProperties(unittest.TestCase):
    """Tests for line1/line2 read-only properties."""

    def test_line_properties_strip_padding(self):
        lcd = LCDDisplay()
        lcd._line1 = "Hello           "
        lcd._line2 = "World           "
        self.assertEqual(lcd.line1, "Hello")
        self.assertEqual(lcd.line2, "World")

    def test_line_properties_empty_when_cleared(self):
        lcd = LCDDisplay()
        self.assertEqual(lcd.line1, "")
        self.assertEqual(lcd.line2, "")

    def test_line_properties_preserve_trailing_spaces_in_content(self):
        lcd = LCDDisplay()
        lcd._line1 = "A  B            "
        self.assertEqual(lcd.line1, "A  B")


if __name__ == "__main__":
    unittest.main()
