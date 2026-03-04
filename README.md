# 🛡️ Room Guard

> A Raspberry Pi 4 motion-detection alarm — a fun project for kids and parents!

## What Does It Do?

When someone walks into the room, the **Room Guard** detects their movement and:
- 💡 Lights up an LED
- 🔊 Sounds a buzzer

After a few seconds, it goes quiet and watches for the next intruder! 🕵️

## What You Need

- Raspberry Pi 4 (any model)
- HC-SR501 PIR motion sensor
- LED + 220Ω resistor
- Active buzzer
- Breadboard + jumper wires
- microSD card (16GB+)

## Quick Start

### 1. Flash the OS
Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/) and flash **Raspberry Pi OS Lite (64-bit)** onto your microSD card. See [docs/DESIGN.md](docs/DESIGN.md#step-1--flash-raspberry-pi-os) for detailed steps.

### 2. Wire the Components
Connect the PIR sensor, LED, and buzzer to the GPIO pins. See the [wiring guide](docs/DESIGN.md#step-3--wiring-the-components).

### 3. Deploy the Code

```bash
ssh yehudalevavi@room-guard.local
cd ~/rpiProject
pip3 install -r requirements.txt
```

### 4. Test the Outputs

Before running the full app, verify your LED and buzzer wiring:

```bash
python3 src/test_outputs.py
```

The LED should light up and the buzzer should sound in sequence. If not, check your wiring (see [troubleshooting](docs/DESIGN.md#troubleshooting)).

### 5. Run It!

```bash
python3 src/room_guard.py
```

Wave your hand in front of the sensor — the LED should light up and the buzzer should sound! 🎉

### 6. Auto-Start on Boot (Optional)

```bash
sudo cp config/room_guard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable room_guard
sudo systemctl start room_guard
```

## Full Documentation

📖 See **[docs/DESIGN.md](docs/DESIGN.md)** for the complete design document including wiring diagrams, architecture, and troubleshooting.

## License

This is a personal learning project. Have fun! 🚀
