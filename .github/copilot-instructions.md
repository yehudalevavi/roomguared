# Copilot Instructions — Room Guard

## Development Roadmap

Feature development follows **[docs/DASHBOARD_PLAN.md](../docs/DASHBOARD_PLAN.md)**. When implementing a feature, refer to its description there for wiring, architecture, and acceptance criteria. If a new feature is not yet described in the plan, add it there before implementing.

## Build & Run

```bash
# Activate venv (Pi or dev machine)
source .venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt

# Run the web dashboard (main entry point)
python3 src/web_app.py

# Run standalone CLI mode (no web UI)
python3 src/room_guard.py
```

## Testing

Tests use `unittest.TestCase` and run with pytest. No Pi hardware needed.

```bash
# Run all unit tests
pytest tests/

# Run a single test file
pytest tests/test_buzzer_unit.py

# Run a single test method
pytest tests/test_web_unit.py::TestWebApp::test_arm_disarm

# Manual hardware smoke tests (Pi only — not automated)
python3 src/test_outputs.py
python3 src/test_buzzer.py
python3 src/test_dht11.py
python3 src/test_lcd.py
```

## Architecture

Single-process Flask app with a hardware controller singleton:

- **`web_app.py`** — Flask routes + REST API. Creates one global `RoomGuard` instance. Hardware starts in a background daemon thread so Flask can serve immediately.
- **`room_guard.py`** — Central orchestrator (`RoomGuard` class). Owns PIR sensor, LED, buzzer, and LCD. Manages armed/disarmed state, motion callbacks, event logging, and LCD page cycling. All shared state is protected by `self._lock`; LCD writes use a separate `self._lcd_lock`.
- **`buzzer.py`** — Passive buzzer PWM driver. Defines note frequency constants (`NOTE_C4`–`NOTE_C6`, `REST`) and system melodies (`MELODY_STARTUP`, `MELODY_ARM`, `MELODY_DISARM`, `MELODY_SENSOR_ERROR`).
- **`melody_library.py`** — 20 named motion-alert melodies. Each melody is `(display_name, [(frequency_hz, duration_seconds), ...])`. Uses note constants from `buzzer.py`.
- **`lcd_display.py`** — HD44780 LCD driver (16×2, 4-bit mode). Caches line contents to skip redundant writes. Text must be ASCII-only, max 16 chars per line. Supports scrolling via `write_at_offset()`.
- **`dht11_sensor.py`** — DHT11 temperature/humidity adapter. Currently standalone — **not integrated** into RoomGuard or the web app.
- **`templates/index.html`** — Single-file dashboard (inline CSS + JS, no build step, no CDN). Default language is Hebrew/RTL with a JS language toggle. Polls `/api/status` every 3s and `/api/logs` every 5s.

## Hardware Abstraction Pattern

All hardware modules use **lazy imports** so they can be imported on non-Pi systems without failing:

```python
def start(self):
    from gpiozero import PWMOutputDevice  # imported only when start() is called
    self._device = PWMOutputDevice(self._pin)
```

Every hardware wrapper follows a **start/stop lifecycle** — calling methods before `start()` raises `RuntimeError`. Preserve this pattern when adding new hardware modules.

## Testing Conventions

Hardware is mocked by injecting `MagicMock` into `sys.modules` **before** importing the module under test:

```python
import sys
from unittest.mock import MagicMock
sys.modules["gpiozero"] = MagicMock()
# NOW import the production module
from buzzer import Buzzer
```

Other conventions:
- Tests use `unittest.TestCase` with `setUp()`, not pytest fixtures or `conftest.py`
- `sys.path.insert(0, "src")` is used at the top of each test file
- Tests freely access private fields (e.g., `guard._armed`, `guard._event_log`) for state verification
- `patch("buzzer.time")` or similar patches bypass real `time.sleep` in tests
- Flask routes are tested via `app.test_client()`

## Key Conventions

- **Lifecycle**: Hardware wrappers must implement `start()` and `stop()`. Initialize hardware in `start()`, not `__init__()`.
- **Thread safety**: Shared state mutations in `RoomGuard` must be inside `with self._lock`. LCD writes use `with self._lcd_lock`.
- **Error handling**: Hardware adapters raise `RuntimeError` for misuse. Higher-level code catches broad `Exception` and degrades gracefully (e.g., software-only mode if hardware init fails).
- **Logging**: Uses `print()` plus an in-memory rolling event log (max 100 entries). No Python `logging` module.
- **LCD text**: ASCII printable only (`0x20`–`0x7E`). Use `LCDDisplay.sanitize()` for validation.
- **Melody format**: `(frequency_hz, duration_seconds)` tuples. Use `REST = 0` for silence. System melodies go in `buzzer.py`; motion melodies go in `melody_library.py`.
- **No build system**: No `pyproject.toml`, `setup.py`, or CI/CD. Deployment is via `git pull` on the Pi (automated by the systemd service on reboot).
- **Frontend**: No framework, no bundler. All JS/CSS is inline in `index.html`.

## Deployment & Device Access

The Raspberry Pi is accessible via SSH for deployment, testing, and troubleshooting:

```bash
ssh yehudalevavi@room-guard.local
```

The agent can and should SSH into the device to:
- **Deploy** — push code and restart the service
- **Test** — run unit tests or manual hardware smoke tests on real hardware
- **Troubleshoot** — check service status, read logs, verify GPIO wiring

Common device operations:

```bash
# Check service status
sudo systemctl status room_guard

# View live service logs
sudo journalctl -u room_guard -f

# Restart after code changes
sudo systemctl restart room_guard

# Run tests on the Pi
cd ~/rpiProject && source .venv/bin/activate && pytest tests/

# Run a manual hardware test
cd ~/rpiProject && source .venv/bin/activate && python3 src/test_buzzer.py
```

The systemd service (`config/room_guard.service`) auto-pulls from `master` and installs dependencies on every start, so a simple `sudo systemctl restart room_guard` deploys the latest code.
