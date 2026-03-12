# 🛡️ Room Guard

> A Raspberry Pi 4 motion-detection alarm with a web dashboard — a fun project for kids and parents!

## What Does It Do?

When someone walks into the room, the **Room Guard** detects their movement and:
- 💡 Lights up an LED
- 🎵 Plays a random famous melody on a passive buzzer (from a library of 20 tunes!)

Each motion event plays a different melody — Mozart, Beethoven, Jingle Bells, and more. The melody name is logged so you can see which one played. After a cooldown, it watches for the next intruder! 🕵️

### 🌐 Web Dashboard

Control everything from your phone or laptop at **`http://room-guard:5000`**:

- **Arm / Disarm** the motion sensor with a single toggle button
- **Toggle the LED** on and off
- **Play any of the 20 melodies** on demand from a dropdown
- **Live status** — motion count, last event, armed state (auto-refreshes)
- **Activity log** — scrollable event log with melody names

No app install needed — just open a browser on any device on your local network.

## What You Need

- Raspberry Pi 4 (any model)
- HC-SR501 PIR motion sensor
- LED + 220Ω resistor
- Passive buzzer (no white sticker on top — unlike the active buzzer)
- Breadboard + jumper wires
- microSD card (16GB+)

## Quick Start

### 1. Flash the OS
Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/) and flash **Raspberry Pi OS Lite (64-bit)** onto your microSD card. See [docs/DESIGN.md](docs/DESIGN.md#step-1--flash-raspberry-pi-os) for detailed steps.

### 2. Wire the Components
Connect the PIR sensor, LED, and passive buzzer to the GPIO pins. See the [wiring guide](docs/DESIGN.md#step-3--wiring-the-components).

### 3. Deploy the Code

```bash
ssh yehudalevavi@room-guard.local
cd ~/rpiProject
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

### 4. Test the Outputs

Before running the full app, verify your LED and buzzer wiring:

```bash
source .venv/bin/activate
python3 src/test_outputs.py   # LED on/off test
python3 src/test_buzzer.py    # Plays system melodies + 3 random samples
```

You should hear distinct tones (not clicks). If you hear clicking, you may have the active buzzer connected — swap it for the passive one. See [troubleshooting](docs/DESIGN.md#troubleshooting).

### 5. Run the Web Dashboard

```bash
source .venv/bin/activate
python3 src/web_app.py
```

Open **`http://room-guard:5000`** in your browser. The dashboard shows status, controls for the sensor/LED/melodies, and a live activity log.

> You can also run the standalone CLI mode (no web UI): `python3 src/room_guard.py`

### 6. Auto-Start on Boot (Optional)

```bash
sudo cp config/room_guard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable room_guard
sudo systemctl start room_guard
```

The web dashboard will start automatically on boot and be available at `http://room-guard:5000`.

> **Auto-update:** On every start (including reboot), the service automatically runs `git pull` and `pip install` to fetch the latest code and dependencies. If the network is unavailable, the service starts normally with the existing code.

## Project Structure

```
src/
├── web_app.py           # Flask web app — serves dashboard + REST API
├── room_guard.py        # Core logic — RoomGuard class (PIR, LED, buzzer)
├── buzzer.py            # Passive buzzer PWM driver + system melodies
├── melody_library.py    # 20 famous melodies for random motion alerts
├── templates/
│   └── index.html       # Web dashboard — dark-themed, responsive, no CDN
├── dht11_sensor.py      # DHT11 temperature sensor module (pending hardware)
├── test_outputs.py      # Hardware test: LED on/off
├── test_buzzer.py       # Hardware test: plays melodies on the buzzer
└── test_dht11.py        # Hardware test: DHT11 sensor readings
tests/
├── test_buzzer_unit.py  # Unit tests for buzzer + melody library (no Pi needed)
├── test_web_unit.py     # Unit tests for web app + RoomGuard class (no Pi needed)
└── test_dht11_unit.py   # Unit tests for DHT11 sensor (no Pi needed)
config/
└── room_guard.service   # systemd service file (runs web_app.py)
```

## Web Dashboard API

The dashboard communicates via a REST API. You can also call these endpoints directly (e.g. with `curl`):

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard HTML page |
| GET | `/api/status` | System state (armed, motion count, LED, etc.) |
| POST | `/api/arm` | Enable motion detection |
| POST | `/api/disarm` | Disable motion detection |
| POST | `/api/led/on` | Turn LED on |
| POST | `/api/led/off` | Turn LED off |
| POST | `/api/play/<name>` | Play a melody by name |
| GET | `/api/melodies` | List all 20 available melody names |
| GET | `/api/logs?limit=50` | Recent activity log entries (JSON) |
| POST | `/api/lcd/message` | Show custom message on LCD for 10 seconds (JSON body: `{"line1":"…","line2":"…"}`) |

## Full Documentation

📖 See **[docs/DESIGN.md](docs/DESIGN.md)** for the complete design document including wiring diagrams, architecture, and troubleshooting.

📋 See **[docs/DASHBOARD_PLAN.md](docs/DASHBOARD_PLAN.md)** for the roadmap to add more components (LCD display, RTC clock, data logging).

## License

This is a personal learning project. Have fun! 🚀
