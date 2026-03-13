#!/usr/bin/env python3
"""
IR remote test utility — prints all received button codes.

Use this to discover the scancodes your remote sends, then
update the mapping in ir_remote.py if needed.

Setup:
    1. Add to /boot/config.txt: dtoverlay=gpio-ir,gpio_pin=18
    2. Reboot the Pi
    3. Run: python3 src/test_ir.py

Press any button on your remote and watch the output.
Press Ctrl+C to exit.
"""


def main():
    try:
        import evdev
    except ImportError:
        print("ERROR: 'evdev' package not installed.")
        print("Install it with: pip3 install evdev")
        return

    # Find the IR input device
    device = None
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        if "ir" in dev.name.lower() or "gpio_ir" in dev.name.lower():
            device = dev
            break
        dev.close()

    if device is None:
        print("ERROR: IR receiver not found!")
        print()
        print("Checklist:")
        print("  1. Is 'dtoverlay=gpio-ir,gpio_pin=18' in /boot/config.txt?")
        print("  2. Have you rebooted after adding the overlay?")
        print("  3. Is the IR receiver wired correctly?")
        print("     Signal → GPIO 18 (Pin 12)")
        print("     VCC    → 3.3V (Pin 1)")
        print("     GND    → GND rail")
        print()
        print("Run 'ir-keytable' to check if the kernel sees the device.")
        return

    print(f"IR device found: {device.name} ({device.path})")
    print()
    print("Point your remote at the IR receiver and press buttons.")
    print("Press Ctrl+C to exit.")
    print()
    print(f"{'Event':<12} {'Code':<28} {'State':<10}")
    print("-" * 50)

    try:
        for event in device.read_loop():
            if event.type == evdev.ecodes.EV_MSC:
                if event.code == evdev.ecodes.MSC_SCAN:
                    print(f"{'SCANCODE':<12} 0x{event.value:04x} ({event.value:<5d})")
            elif event.type == evdev.ecodes.EV_KEY:
                key_name = evdev.ecodes.KEY.get(event.code, f"UNKNOWN_{event.code}")
                if isinstance(key_name, list):
                    key_name = key_name[0]
                state = {0: "released", 1: "pressed", 2: "held"}.get(
                    event.value, str(event.value)
                )
                print(f"{'KEY':<12} {key_name:<28} {state}")
    except KeyboardInterrupt:
        print("\nDone.")
    finally:
        device.close()


if __name__ == "__main__":
    main()
