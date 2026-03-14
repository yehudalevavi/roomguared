#!/usr/bin/env python3
"""
Room Guard — Web-based control panel.

Flask application that serves a dashboard UI and REST API to control
the Room Guard motion detection system from any browser on the local network.

Usage:
    python3 src/web_app.py          # Development mode
    Access at http://room-guard:5000
"""

import signal
import sys
import threading
import time

from flask import Flask, jsonify, render_template, request

from room_guard import RoomGuard
from buzzer import MELODY_STARTUP

app = Flask(__name__)
guard = RoomGuard()
ir_remote = None
nfc_reader = None


# --- HTML Dashboard ---

@app.route("/")
def index():
    """Serve the dashboard page."""
    return render_template("index.html")


# --- REST API ---

@app.route("/api/status")
def api_status():
    """Return current system state."""
    return jsonify(guard.get_status())


@app.route("/api/arm", methods=["POST"])
def api_arm():
    """Enable motion detection."""
    guard.arm()
    return jsonify({"ok": True, "armed": True})


@app.route("/api/disarm", methods=["POST"])
def api_disarm():
    """Disable motion detection."""
    guard.disarm()
    return jsonify({"ok": True, "armed": False})


@app.route("/api/led/on", methods=["POST"])
def api_led_on():
    """Turn LED on."""
    guard.set_led(True)
    return jsonify({"ok": True, "led_on": True})


@app.route("/api/led/off", methods=["POST"])
def api_led_off():
    """Turn LED off."""
    guard.set_led(False)
    return jsonify({"ok": True, "led_on": False})


@app.route("/api/play/<name>", methods=["POST"])
def api_play(name):
    """Play a specific melody by name."""
    found = guard.play_melody_by_name(name)
    if not found:
        return jsonify({"ok": False, "error": "Melody not found or buzzer busy"}), 404
    return jsonify({"ok": True, "melody": name})


@app.route("/api/melodies")
def api_melodies():
    """List all available melody names."""
    return jsonify({"melodies": guard.get_melody_names()})


@app.route("/api/logs")
def api_logs():
    """Return recent log entries."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"logs": guard.get_logs(limit)})


@app.route("/api/lcd/message", methods=["POST"])
def api_lcd_message():
    """Show a custom message on the LCD for 10 seconds."""
    data = request.get_json(silent=True) or {}
    line1 = data.get("line1", "")
    line2 = data.get("line2", "")
    if not line1 and not line2:
        return jsonify({"ok": False, "error": "Provide at least line1 or line2"}), 400
    # Validate: only ASCII printable characters (HD44780 LCD)
    from lcd_display import LCDDisplay
    if line1 != LCDDisplay.sanitize(line1) or line2 != LCDDisplay.sanitize(line2):
        return jsonify({"ok": False, "error": "Unsupported characters. Use ASCII only (A-Z, 0-9, symbols)."}), 400
    guard.show_custom_message(line1[:16], line2[:16])
    return jsonify({"ok": True, "line1": line1[:16], "line2": line2[:16]})


@app.route("/api/melody/next", methods=["POST"])
def api_melody_next():
    """Select the next melody."""
    name = guard.next_melody()
    return jsonify({"ok": True, "melody": name})


@app.route("/api/melody/prev", methods=["POST"])
def api_melody_prev():
    """Select the previous melody."""
    name = guard.prev_melody()
    return jsonify({"ok": True, "melody": name})


@app.route("/api/melody/play", methods=["POST"])
def api_melody_play():
    """Play the currently selected melody."""
    name = guard.play_current_melody()
    return jsonify({"ok": True, "melody": name})


@app.route("/api/melody/stop", methods=["POST"])
def api_melody_stop():
    """Stop the currently playing melody."""
    guard.stop_melody()
    return jsonify({"ok": True})


@app.route("/api/toggle-arm", methods=["POST"])
def api_toggle_arm():
    """Toggle arm/disarm with sound cue."""
    armed = guard.toggle_arm()
    return jsonify({"ok": True, "armed": armed})


# --- NFC API ---

@app.route("/api/nfc/cards")
def api_nfc_cards():
    """List all registered NFC cards."""
    if nfc_reader is None:
        return jsonify({"ok": True, "cards": [], "available": False})
    cards = nfc_reader.get_registered_cards()
    return jsonify({"ok": True, "cards": cards, "available": True})


@app.route("/api/nfc/register", methods=["POST"])
def api_nfc_register():
    """Register a new NFC card mapping."""
    if nfc_reader is None:
        return jsonify({"ok": False, "error": "NFC reader not available"}), 503
    data = request.get_json(silent=True) or {}
    uid = data.get("uid", "").strip()
    action = data.get("action", "").strip()
    label = data.get("label", "").strip()
    if not uid or not action:
        return jsonify({"ok": False, "error": "uid and action are required"}), 400
    valid_actions = ["toggle_arm", "toggle_led", "play_random", "stop_melody",
                     "next_melody", "prev_melody"]
    if action not in valid_actions and not action.startswith("play_melody:"):
        return jsonify({"ok": False, "error": f"Invalid action. Valid: {valid_actions} or play_melody:<name>"}), 400
    nfc_reader.register_card(uid, action, label)
    return jsonify({"ok": True, "uid": uid, "action": action, "label": label})


@app.route("/api/nfc/scan", methods=["POST"])
def api_nfc_scan():
    """Enter scan mode: wait for the next card tap and return its UID."""
    if nfc_reader is None:
        return jsonify({"ok": False, "error": "NFC reader not available"}), 503
    data = request.get_json(silent=True) or {}
    timeout = min(data.get("timeout", 15), 30)
    uid = nfc_reader.wait_for_scan(timeout=timeout)
    if uid is None:
        return jsonify({"ok": False, "error": "No card detected (timeout)"}), 408
    return jsonify({"ok": True, "uid": uid})


@app.route("/api/nfc/scan/start", methods=["POST"])
def api_nfc_scan_start():
    """Enter scan mode without blocking. Poll /api/nfc/scan/result for outcome."""
    if nfc_reader is None:
        return jsonify({"ok": False, "error": "NFC reader not available"}), 503
    data = request.get_json(silent=True) or {}
    timeout = min(data.get("timeout", 15), 30)
    nfc_reader.start_scan_mode(timeout=timeout)
    return jsonify({"ok": True})


@app.route("/api/nfc/scan/result")
def api_nfc_scan_result():
    """Poll for the result of an active scan mode."""
    if nfc_reader is None:
        return jsonify({"ok": False, "error": "NFC reader not available"}), 503
    result = nfc_reader.get_scan_result()
    return jsonify({"ok": True, **result})


@app.route("/api/nfc/cards/<path:uid>", methods=["DELETE"])
def api_nfc_remove(uid):
    """Remove a registered NFC card."""
    if nfc_reader is None:
        return jsonify({"ok": False, "error": "NFC reader not available"}), 503
    removed = nfc_reader.remove_card(uid)
    if not removed:
        return jsonify({"ok": False, "error": "Card not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/nfc/last-scan")
def api_nfc_last_scan():
    """Return the last scanned NFC card UID and timestamp."""
    if nfc_reader is None:
        return jsonify({"ok": True, "last_scan": None, "available": False})
    scan = nfc_reader.get_last_scan()
    return jsonify({"ok": True, "last_scan": scan, "available": True})


# --- Startup ---

def start_guard():
    """Initialize hardware and auto-arm after calibration."""
    global ir_remote, nfc_reader
    try:
        guard.start()
    except Exception as e:
        print(f"[Web App] WARNING: Could not initialize hardware: {e}")
        print("[Web App] Running in software-only mode (no GPIO).")
        return

    # Start IR remote (non-fatal if unavailable)
    try:
        from ir_remote import IRRemote
        ir_remote = IRRemote(guard)
        ir_remote.start()
        guard._log_message("IR remote control active")
    except Exception as e:
        print(f"[Web App] IR remote not available: {e}")

    # Start NFC reader (non-fatal if unavailable)
    try:
        from nfc_reader import NFCReader
        nfc_reader = NFCReader(guard)
        nfc_reader.start()
        guard._log_message("NFC card reader active")
    except Exception as e:
        print(f"[Web App] NFC reader not available: {e}")

    guard._buzzer.play_melody(MELODY_STARTUP)
    guard._log_message("PIR sensor calibrating (40s)...")
    time.sleep(40)
    guard._log_message("PIR sensor ready!")
    guard.arm()


def shutdown_handler(signum=None, frame=None):
    """Clean shutdown on SIGINT/SIGTERM."""
    print()
    if nfc_reader:
        nfc_reader.stop()
    if ir_remote:
        ir_remote.stop()
    guard.stop()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Start hardware in a background thread so Flask can serve immediately
    hw_thread = threading.Thread(target=start_guard, daemon=True)
    hw_thread.start()

    print("[Web App] Starting on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
