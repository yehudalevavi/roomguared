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
    D7  → RPi Pin 23 (GPIO 11)
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
LCD_D7 = 11   # Data bit 7 — Pin 23

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

    def write(self, line1: str = "", line2: str = "") -> None:
        """
        Write text to the LCD.

        Args:
            line1: Text for the top row (max 16 characters, truncated if longer).
            line2: Text for the bottom row (max 16 characters, truncated if longer).
        """
        if self._lcd is None:
            raise RuntimeError("LCD not started. Call start() first.")

        line1 = self._pad(line1)
        line2 = self._pad(line2)

        # Only rewrite lines that changed to reduce flicker
        if line1 != self._line1:
            self._lcd.cursor_pos = (0, 0)
            self._lcd.write_string(line1)
            self._line1 = line1

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

    def _pad(self, text: str) -> str:
        """Truncate to LCD width and pad with spaces to overwrite old text."""
        return text[:self.cols].ljust(self.cols)

    def scroll_text(self, line1: str = "", line2: str = "",
                    delay: float = 0.35, pause: float = 1.5,
                    check_stop=None) -> None:
        """
        Display text with horizontal scrolling for lines longer than LCD width.

        Short lines (≤16 chars) are displayed normally. Long lines scroll
        left so the full text can be read, then snap back.

        Args:
            line1: Text for the top row.
            line2: Text for the bottom row.
            delay: Seconds between each scroll step.
            pause: Seconds to pause at start and end of scroll.
            check_stop: Optional callable returning True to abort early.
        """
        if self._lcd is None:
            raise RuntimeError("LCD not started. Call start() first.")

        needs_scroll_1 = len(line1) > self.cols
        needs_scroll_2 = len(line2) > self.cols

        if not needs_scroll_1 and not needs_scroll_2:
            self.write(line1, line2)
            return

        # Pad short lines so they don't scroll
        pad1 = line1 if needs_scroll_1 else line1[:self.cols]
        pad2 = line2 if needs_scroll_2 else line2[:self.cols]

        max_offset = max(
            len(pad1) - self.cols if needs_scroll_1 else 0,
            len(pad2) - self.cols if needs_scroll_2 else 0,
        )

        # Show start position with a pause
        self.write(pad1[:self.cols], pad2[:self.cols])
        for _ in range(int(pause / 0.1)):
            if check_stop and check_stop():
                return
            import time
            time.sleep(0.1)

        # Scroll left one character at a time
        for offset in range(1, max_offset + 1):
            if check_stop and check_stop():
                return
            w1 = pad1[offset:offset + self.cols] if needs_scroll_1 else pad1
            w2 = pad2[offset:offset + self.cols] if needs_scroll_2 else pad2
            self.write(w1.ljust(self.cols), w2.ljust(self.cols))
            import time
            time.sleep(delay)

        # Pause at the end
        for _ in range(int(pause / 0.1)):
            if check_stop and check_stop():
                return
            import time
            time.sleep(0.1)
