#!/usr/bin/env python3
"""
IR remote control handler for Room Guard.

Uses the Linux gpio-ir-recv kernel overlay and evdev to receive
IR signals from a NEC-protocol remote control. Runs a background
thread that listens for button presses and dispatches actions to
the RoomGuard instance.

Setup:
    1. Add to /boot/config.txt: dtoverlay=gpio-ir,gpio_pin=18
    2. Reboot the Pi
    3. Install: sudo apt install -y ir-keytable
    4. Verify: ir-keytable (should show gpio_ir_recv device)

Wiring:
    IR receiver Signal → RPi Pin 12 (GPIO 18)
    IR receiver VCC    → RPi Pin 1 (3.3V)
    IR receiver GND    → Breadboard − rail (GND)
"""

import threading
import time

IR_PIN = 18  # GPIO 18 (Physical pin 12) — default for gpio-ir overlay
DEBOUNCE_MS = 600  # Ignore repeated scancodes within this window

# Default scancode-to-action mapping for the Elegoo NEC remote.
# Run `python3 src/test_ir.py` to discover your remote's actual scancodes.
ELEGOO_SCANCODE_MAP = {
    0x44: "prev_melody",     # |<< button
    0x43: "next_melody",     # >|| button
    0x40: "play_pause",      # >>| button
    0x45: "toggle_arm",      # CH- button (top-left — acts as the "red button")
}


class IRRemote:
    """
    IR remote control listener.

    Reads NEC remote button presses via the Linux input subsystem (evdev)
    and dispatches actions to a RoomGuard instance. The listener runs in
    a background daemon thread.
    """

    def __init__(self, guard, scancode_map=None):
        self._guard = guard
        self._scancode_map = scancode_map if scancode_map is not None else dict(ELEGOO_SCANCODE_MAP)
        self._device = None
        self._running = False
        self._thread = None
        self._last_scancode = None
        self._last_time = 0.0

    def start(self) -> None:
        """Find the IR input device and start the listener thread."""
        self._device = self._find_ir_device()
        if self._device is None:
            raise RuntimeError(
                "IR receiver not found. Ensure dtoverlay=gpio-ir,gpio_pin=18 "
                "is in /boot/config.txt and you have rebooted."
            )
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the listener thread and release the device."""
        self._running = False
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None

    @staticmethod
    def _find_ir_device():
        """Search /dev/input/ for the gpio_ir_recv input device."""
        import evdev
        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            if "ir" in dev.name.lower() or "gpio_ir" in dev.name.lower():
                return dev
            dev.close()
        return None

    def _listen_loop(self) -> None:
        """Background thread: read IR events and dispatch actions."""
        import evdev
        try:
            for event in self._device.read_loop():
                if not self._running:
                    break
                # Use MSC_SCAN events for reliable scancode-based mapping
                # (independent of ir-keytable keymap configuration)
                if (event.type == evdev.ecodes.EV_MSC
                        and event.code == evdev.ecodes.MSC_SCAN):
                    now = time.monotonic()
                    scancode = event.value
                    # Debounce: NEC protocol fires the scancode twice per
                    # button press (initial + repeat). Ignore duplicates
                    # within the debounce window.
                    if (scancode == self._last_scancode
                            and (now - self._last_time) < DEBOUNCE_MS / 1000):
                        continue
                    self._last_scancode = scancode
                    self._last_time = now
                    action = self._scancode_map.get(scancode)
                    if action:
                        self._dispatch(action)
                        # Reset timer after action completes — some actions
                        # block (e.g. toggle_arm plays a melody), and NEC
                        # repeats queued during that time would otherwise
                        # pass the debounce check.
                        self._last_time = time.monotonic()
        except OSError:
            pass  # device closed during stop()
        except Exception as e:
            if self._running:
                print(f"[IR Remote] Error in listener: {e}")

    def _dispatch(self, action: str) -> None:
        """Execute a mapped action on the RoomGuard."""
        try:
            if action == "prev_melody":
                name = self._guard.prev_melody()
                print(f"[IR Remote] Previous: {name}")
            elif action == "next_melody":
                name = self._guard.next_melody()
                print(f"[IR Remote] Next: {name}")
            elif action == "play_pause":
                if self._guard._playing:
                    self._guard.stop_melody()
                    print("[IR Remote] Stopped playback")
                else:
                    name = self._guard.play_current_melody()
                    print(f"[IR Remote] Playing: {name}")
            elif action == "toggle_arm":
                armed = self._guard.toggle_arm()
                state = "Armed" if armed else "Disarmed"
                print(f"[IR Remote] {state}")
        except Exception as e:
            print(f"[IR Remote] Action '{action}' failed: {e}")
