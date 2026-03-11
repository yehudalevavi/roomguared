# 🛡️ Room Guard

> A Raspberry Pi 4 motion-detection alarm — a fun project for kids and parents!

## What Does It Do?

When someone walks into the room, the **Room Guard** detects their movement and:
- 💡 Lights up an LED
- 🎵 Plays a random famous melody on a passive buzzer (from a library of 20 tunes!)

Each motion event plays a different melody — Mozart, Beethoven, Jingle Bells, and more. The melody name is logged so you can see which one played. After a cooldown, it watches for the next intruder! 🕵️

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

### 5. Run It!

```bash
source .venv/bin/activate
python3 src/room_guard.py
```

Wave your hand in front of the sensor — the LED lights up and a random melody plays! 🎶

### 6. Auto-Start on Boot (Optional)

```bash
sudo cp config/room_guard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable room_guard
sudo systemctl start room_guard
```

## Project Structure

```
src/
├── room_guard.py        # Main application — PIR detection + LED + buzzer
├── buzzer.py            # Passive buzzer PWM driver + system melodies
├── melody_library.py    # 20 famous melodies for random motion alerts
├── dht11_sensor.py      # DHT11 temperature sensor module (pending hardware)
├── test_outputs.py      # Hardware test: LED on/off
├── test_buzzer.py       # Hardware test: plays melodies on the buzzer
└── test_dht11.py        # Hardware test: DHT11 sensor readings
tests/
├── test_buzzer_unit.py  # Unit tests for buzzer + melody library (no Pi needed)
└── test_dht11_unit.py   # Unit tests for DHT11 sensor (no Pi needed)
```

## Full Documentation

📖 See **[docs/DESIGN.md](docs/DESIGN.md)** for the complete design document including wiring diagrams, architecture, and troubleshooting.

📋 See **[docs/DASHBOARD_PLAN.md](docs/DASHBOARD_PLAN.md)** for the roadmap to add more components (LCD display, RTC clock, data logging).

## License

This is a personal learning project. Have fun! 🚀
