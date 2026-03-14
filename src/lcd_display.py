#!/usr/bin/env python3
"""
LCD1602 display module (4-bit parallel mode).

Provides a clean interface to write text on a 16x2 character LCD,
with automatic text truncation and a start/stop lifecycle matching
the other hardware modules in this project.

Wiring (see DESIGN.md for full details):
    RS  → RPi Pin 37 (GPIO 26)
    E   → RPi Pin 35 (GPIO 19)
    D4  → RPi Pin 33 (GPIO 13)
    D5  → RPi Pin 31 (GPIO 6)
    D6  → RPi Pin 29 (GPIO 5)
    D7  → RPi Pin 32 (GPIO 12)
    VSS → GND rail, VDD → 5V rail, RW → GND rail
    V0  → Potentiometer wiper (contrast)
    A   → 5V rail via 220Ω, K → GND rail (backlight)
"""

# GPIO pin assignments (BCM numbering)
LCD_RS = 26   # Register Select — Pin 37
LCD_E = 19    # Enable — Pin 35
LCD_D4 = 13   # Data bit 4 — Pin 33
LCD_D5 = 6    # Data bit 5 — Pin 31
LCD_D6 = 5    # Data bit 6 — Pin 29
LCD_D7 = 12   # Data bit 7 — Pin 32 (reassigned from GPIO 11 for NFC SPI)

LCD_COLS = 16  # characters per line
LCD_ROWS = 2   # number of lines


class LCDDisplay:
    """
    LCD1602 controller using RPLCD in 4-bit GPIO mode.

    Call start() before writing, and stop() when done.
    """

    def __init__(self, rs=LCD_RS, e=LCD_E, d4=LCD_D4, d5=LCD_D5,
                 d6=LCD_D6, d7=LCD_D7, cols=LCD_COLS, rows=LCD_ROWS):
        self.rs = rs
        self.e = e
        self.data_pins = [d4, d5, d6, d7]
        self.cols = cols
        self.rows = rows
        self._lcd = None
        self._line1 = ""
        self._line2 = ""

    def start(self) -> None:
        """Initialize the LCD hardware."""
        from RPLCD.gpio import CharLCD
        import RPi.GPIO as GPIO

        self._lcd = CharLCD(
            numbering_mode=GPIO.BCM,
            cols=self.cols,
            rows=self.rows,
            pin_rs=self.rs,
            pin_e=self.e,
            pins_data=self.data_pins,
            compat_mode=True,
        )
        self._lcd.clear()

    def stop(self) -> None:
        """Clear the display and release hardware."""
        if self._lcd is not None:
            self._lcd.clear()
            self._lcd.close(clear=True)
            self._lcd = None
            self._line1 = ""
            self._line2 = ""

    def write(self, line1: str | None = None, line2: str | None = None) -> None:
        """
        Write text to the LCD.

        Args:
            line1: Text for the top row (max 16 chars). None = don't change.
            line2: Text for the bottom row (max 16 chars). None = don't change.
        """
        if self._lcd is None:
            raise RuntimeError("LCD not started. Call start() first.")

        if line1 is not None:
            line1 = self._pad(line1)
            if line1 != self._line1:
                self._lcd.cursor_pos = (0, 0)
                self._lcd.write_string(line1)
                self._line1 = line1

        if line2 is not None:
            line2 = self._pad(line2)
            if line2 != self._line2:
                self._lcd.cursor_pos = (1, 0)
                self._lcd.write_string(line2)
                self._line2 = line2

    def clear(self) -> None:
        """Clear both lines of the display."""
        if self._lcd is None:
            raise RuntimeError("LCD not started. Call start() first.")

        self._lcd.clear()
        self._line1 = ""
        self._line2 = ""

    @property
    def line1(self) -> str:
        """Return the current text on line 1."""
        return self._line1.rstrip()

    @property
    def line2(self) -> str:
        """Return the current text on line 2."""
        return self._line2.rstrip()

    # ASCII printable range supported by the HD44780 controller
    _LCD_SAFE_RANGE = range(0x20, 0x7F)  # space … tilde

    @classmethod
    def sanitize(cls, text: str) -> str:
        """Strip characters unsupported by the HD44780 LCD controller.

        Keeps only ASCII printable characters (0x20–0x7E).
        """
        return "".join(c for c in text if ord(c) in cls._LCD_SAFE_RANGE)

    def _pad(self, text: str) -> str:
        """Truncate to LCD width and pad with spaces to overwrite old text."""
        return text[:self.cols].ljust(self.cols)

    def write_at_offset(self, text: str, row: int, offset: int) -> None:
        """Write a substring of text at the given offset on the given row."""
        if self._lcd is None:
            raise RuntimeError("LCD not started. Call start() first.")
        window = text[offset:offset + self.cols].ljust(self.cols)
        target = f"_line{row + 1}"
        if getattr(self, target) != window:
            self._lcd.cursor_pos = (row, 0)
            self._lcd.write_string(window)
            setattr(self, target, window)
