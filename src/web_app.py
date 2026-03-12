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
    guard.show_custom_message(line1, line2)
    return jsonify({"ok": True, "line1": line1, "line2": line2})


# --- Startup ---

def start_guard():
    """Initialize hardware and auto-arm after calibration."""
    try:
        guard.start()
    except Exception as e:
        print(f"[Web App] WARNING: Could not initialize hardware: {e}")
        print("[Web App] Running in software-only mode (no GPIO).")
        return

    guard._buzzer.play_melody(MELODY_STARTUP)
    guard._log_message("PIR sensor calibrating (40s)...")
    time.sleep(40)
    guard._log_message("PIR sensor ready!")
    guard.arm()


def shutdown_handler(signum=None, frame=None):
    """Clean shutdown on SIGINT/SIGTERM."""
    print()
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
