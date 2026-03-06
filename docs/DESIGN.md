# 🛡️ Room Guard — Design Document

> A Raspberry Pi 4 project for kids and parents: detect motion, flash a light, sound an alarm!

---

## Table of Contents

1. [Overview](#overview)
2. [Components List](#components-list)
3. [Step 1 — Flash Raspberry Pi OS](#step-1--flash-raspberry-pi-os)
4. [Step 2 — Initial Raspberry Pi Setup](#step-2--initial-raspberry-pi-setup)
5. [Step 3 — Wiring the Components](#step-3--wiring-the-components)
6. [Step 4 — Deploy and Run the Application](#step-4--deploy-and-run-the-application)
7. [Step 5 — Auto-Start on Boot](#step-5--auto-start-on-boot)
8. [Application Architecture](#application-architecture)
9. [Debugging on the Raspberry Pi](#debugging-on-the-raspberry-pi)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The **Room Guard** is a motion-detection alarm system. When someone enters the room, a PIR (Passive Infrared) sensor detects their body heat, and the Raspberry Pi responds by:

- 💡 Turning on an LED
- 🔊 Sounding a buzzer

After a cooldown period (default: 5 seconds), both turn off and the system is ready to detect again.

---

## Components List

| # | Component              | Qty | Approx. Cost | Notes                                  |
|---|------------------------|-----|-------------|----------------------------------------|
| 1 | Raspberry Pi 4         | 1   | —           | Any RAM variant (2GB/4GB/8GB)          |
| 2 | microSD card (16GB+)   | 1   | —           | Class 10 or faster                     |
| 3 | USB-C power supply     | 1   | —           | 5V/3A official RPi PSU recommended     |
| 4 | HC-SR501 PIR sensor    | 1   | ~$2         | 3-pin: VCC, OUT, GND                   |
| 5 | LED (any color)        | 1   | ~$0.10      | Standard 5mm through-hole              |
| 6 | 220Ω resistor          | 1   | ~$0.05      | ¼W, for LED current limiting           |
| 7 | Active buzzer          | 1   | ~$1         | 3V–5V operating voltage                |
| 8 | Breadboard             | 1   | ~$3         | Half-size or full-size                  |
| 9 | Jumper wires (Male-to-Female) | ~10 | ~$2  | For connecting RPi GPIO to breadboard  |

---

## Step 1 — Flash Raspberry Pi OS

### What you need
- A computer (Windows, Mac, or Linux)
- A microSD card + card reader
- Internet connection

### Instructions

1. **Download** [Raspberry Pi Imager](https://www.raspberrypi.com/software/) and install it.

2. **Open** Raspberry Pi Imager.

3. **Choose OS**: Click "Choose OS" → "Raspberry Pi OS (other)" → **"Raspberry Pi OS Lite (64-bit)"**.
   > We use the Lite version (no desktop) because our Room Guard doesn't need a screen — it's a dedicated sensor device.

4. **Choose Storage**: Select your microSD card.

5. **Configure settings** (click the ⚙️ gear icon):
   - ☑️ Set hostname: `room-guard`
   - ☑️ Enable SSH → Use password authentication
   - ☑️ Set username and password (e.g., `pi` / `your-password`)
   - ☑️ Configure Wi-Fi:
     - SSID: your Wi-Fi network name
     - Password: your Wi-Fi password
     - Country: your country code (e.g., IL, US, GB)
   - ☑️ Set locale: your timezone and keyboard layout

6. **Click "Write"** and wait for the flash + verification to complete.

7. **Insert** the microSD card into the Raspberry Pi 4.

8. **Power on** the Raspberry Pi (plug in the USB-C power supply).

9. **Wait ~60 seconds** for the first boot to complete.

---

## Step 2 — Initial Raspberry Pi Setup

### Connect via SSH

From your computer's terminal:

```bash
ssh yehudalevavi@room-guard.local
```

> If `room-guard.local` doesn't work, find the Pi's IP address from your router's admin page and use `ssh yehudalevavi@<IP_ADDRESS>`.

### Update the system

```bash
sudo apt update && sudo apt upgrade -y
```

### Install required packages

```bash
sudo apt install -y python3-pip python3-venv git
```

### Verify GPIO access

```bash
pinout
```

This should display a diagram of your Raspberry Pi's GPIO pins. If it doesn't work, enable GPIO via:

```bash
sudo raspi-config
# Navigate to: Interface Options → GPIO → Enable
```

### Ensure your user has GPIO permissions

```bash
sudo usermod -aG gpio $USER
```

Log out and back in for the group change to take effect.

---

## Step 3 — Wiring the Components

### Breadboard Power Rails

Instead of running individual power/ground wires from each component back to the Raspberry Pi, we use the breadboard's **power rails** (the long `+` and `−` strips along the edges):

1. Connect **one wire** from RPi **Pin 2 (5V)** → breadboard **+ rail** (red strip)
2. Connect **one wire** from RPi **Pin 6 (GND)** → breadboard **− rail** (blue strip)

All components then tap power and ground from these rails. This keeps wiring clean and uses only 2 RPi pins for power instead of many.

> 💡 Most full-size breadboards have rails on **both sides**. If your wires need to reach both sides, add a short jumper bridging the left `+` to right `+` rail, and left `−` to right `−` rail.

### GPIO Pin Assignments (BCM Numbering)

| Component        | GPIO Pin  | Physical Pin | Direction |
|------------------|-----------|-------------|-----------|
| 5V Power Rail    | —         | Pin 2 (5V)  | POWER     |
| GND Rail         | —         | Pin 6 (GND) | GROUND    |
| PIR Sensor OUT   | GPIO 17   | Pin 11      | INPUT     |
| LED (+) via 220Ω | GPIO 27   | Pin 13      | OUTPUT    |
| Buzzer (+)       | GPIO 22   | Pin 15      | OUTPUT    |
| DHT11 DATA       | GPIO 4    | Pin 7       | INPUT     |

> All component VCC pins connect to the breadboard **+ rail**, and all GND pins to the **− rail**.

### Wiring Diagram

```
    Raspberry Pi 4 GPIO Header
    (Pin 1 = top-left, Pin 2 = top-right)

    3V3  (1) (2)  5V ─────────────────── Breadboard + rail (red)
  GPIO2  (3) (4)  5V
  GPIO3  (5) (6)  GND ────────────────── Breadboard − rail (blue)
         ┌──────────────────────────────── DHT11 DATA (yellow wire)
  GPIO4  (7) (8)  GPIO14
    GND  (9) (10) GPIO15
         ┌──────────────────────────────── PIR OUT (yellow wire)
  GPIO17 (11)(12) GPIO18
         ┌──────────────────────────────── LED Anode (+) via 220Ω resistor
  GPIO27 (13)(14) GND
         ┌──────────────────────────────── Buzzer (+)
  GPIO22 (15)(16) GPIO23
    3V3  (17)(18) GPIO24


    Breadboard (830 tie-points)
    ┌──────────────────────────────────────────────┐
    │  + rail ──── 5V from RPi Pin 2               │
    │  − rail ──── GND from RPi Pin 6              │
    │                                               │
    │  PIR VCC ────── + rail                        │
    │  PIR GND ────── − rail                        │
    │                                               │
    │  LED (−) ────── − rail                        │
    │                                               │
    │  Buzzer (−) ─── − rail                        │
    │                                               │
    │  DHT11 (+) ──── + rail                        │
    │  DHT11 (−) ──── − rail                        │
    └──────────────────────────────────────────────┘
```

### Step-by-Step Wiring

> ⚠️ **Always wire with the Raspberry Pi powered OFF!**

#### Step A — Breadboard Power Rails
1. Connect RPi **Pin 2 (5V)** to the breadboard **+ rail** (red strip) using a red jumper wire.
2. Connect RPi **Pin 6 (GND)** to the breadboard **− rail** (blue strip) using a black jumper wire.
3. If using both sides of the breadboard, bridge the `+` rails together and the `−` rails together with short jumper wires.

#### PIR Sensor (HC-SR501)
1. Connect **VCC** (usually the left pin, marked +) to the breadboard **+ rail**.
2. Connect **OUT** (middle pin) to **Pin 11 (GPIO 17)** using a yellow/green jumper wire.
3. Connect **GND** (right pin, marked −) to the breadboard **− rail**.

#### LED
1. Place the LED on the breadboard.
2. Connect a **220Ω resistor** from **Pin 13 (GPIO 27)** to the LED's **long leg (anode, +)**.
3. Connect the LED's **short leg (cathode, −)** to the breadboard **− rail**.

#### Active Buzzer
1. Place the buzzer on the breadboard.
2. Connect the buzzer's **(+) pin** to **Pin 15 (GPIO 22)**.
3. Connect the buzzer's **(−) pin** to the breadboard **− rail**.

#### DHT11 Temperature & Humidity Sensor
1. The DHT11 module (from the Elegoo kit) has 3 pins labeled **+**, **out**, and **−**.
2. Connect **+** (VCC) to the breadboard **+ rail**.
3. Connect **out** (DATA) to **Pin 7 (GPIO 4)** using a yellow/green jumper wire.
4. Connect **−** (GND) to the breadboard **− rail**.

> The Elegoo DHT11 module has a built-in 10KΩ pull-up resistor — no extra resistor needed.

##### Testing the DHT11

After wiring, run the hardware test:

```bash
source .venv/bin/activate
python3 src/test_dht11.py
```

You should see 10 readings with temperature (°C) and humidity (%). At least 8/10 should succeed. If not, check the [Troubleshooting](#troubleshooting) section.

### PIR Sensor Adjustment

The HC-SR501 has two small orange potentiometers on its back:

- **Sensitivity (left)**: Turn clockwise to increase detection range (up to ~7m). Start at mid-point.
- **Time delay (right)**: How long the output stays HIGH after detection. Turn fully counter-clockwise for minimum (~2.5s). Our software handles the rest.

There's also a jumper:
- **H position** (default): Repeatable trigger — re-triggers while motion continues.
- **L position**: Single trigger — triggers once, then waits for delay.

👉 **Recommended**: Leave jumper on **H** and both pots at mid-point.

---

## Step 4 — Deploy and Run the Application

### Clone the project

On your Raspberry Pi:

```bash
cd ~
git clone <your-repo-url> rpiProject
cd rpiProject
```

Or copy files via SCP from your computer:

```bash
scp -r src/ config/ requirements.txt yehudalevavi@room-guard:~/rpiProject/
```

### Install dependencies

> **Note:** The venv must be created with `--system-site-packages` so it can access the system-installed `lgpio` package (required by `gpiozero`).

```bash
cd ~/rpiProject
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
sudo apt install -y libgpiod2
pip3 install -r requirements.txt
```

### Test the outputs

Before running the full application, verify that the LED and buzzer are wired correctly:

```bash
source .venv/bin/activate
python3 src/test_outputs.py
```

You should see:

```
=== Output Test ===

1) LED on for 2 seconds...
   LED off.

2) Buzzer on for 1 second...
   Buzzer off.

3) Both on together for 2 seconds...
   Both off.

=== Test complete ===
```

If the LED doesn't light up or the buzzer doesn't sound, check the [Troubleshooting](#troubleshooting) section.

### Run manually

```bash
source .venv/bin/activate
python3 src/room_guard.py
```

You should see:

```
[Room Guard] Starting up...
[Room Guard] PIR sensor on GPIO 17
[Room Guard] LED on GPIO 27
[Room Guard] Buzzer on GPIO 22
[Room Guard] Waiting for motion...
```

Wave your hand in front of the PIR sensor. You should see:

```
[Room Guard] 2026-03-04 14:30:05 — MOTION DETECTED!
```

Press **Ctrl+C** to stop.

---

## Step 5 — Auto-Start on Boot

### Install the systemd service

```bash
sudo cp config/room_guard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable room_guard
sudo systemctl start room_guard
```

### Check status

```bash
sudo systemctl status room_guard
```

### View logs

```bash
journalctl -u room_guard -f
```

### Stop the service

```bash
sudo systemctl stop room_guard
```

---

## Application Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌───────────┐
│   HC-SR501      │  RISING │                  │  HIGH   │   LED     │
│   PIR Sensor    │────────▶│   room_guard.py  │────────▶│  GPIO 27  │
│   (GPIO 17)     │  EDGE   │                  │         └───────────┘
└─────────────────┘         │  1. Detect       │         ┌───────────┐
                            │  2. Alert ON     │  HIGH   │  Buzzer   │
                            │  3. Wait cooldown│────────▶│  GPIO 22  │
                            │  4. Alert OFF    │         └───────────┘
                            │  5. Log event    │
                            └──────────────────┘
```

### How it works

1. **Initialization**: Set up GPIO devices using `gpiozero` (MotionSensor for PIR, LED and OutputDevice for outputs). Register a motion callback on the PIR sensor.
2. **Waiting**: The main thread sleeps while `gpiozero` watches for motion on GPIO 17.
3. **Motion detected**: The callback fires — LED and buzzer are turned ON. A timestamp is logged.
4. **Cooldown**: After the configured cooldown period (default 5s), LED and buzzer are turned OFF.
5. **Repeat**: System returns to waiting state.
6. **Shutdown**: On SIGINT (Ctrl+C) or SIGTERM (systemd stop), all GPIO pins are cleaned up.

---

## Debugging on the Raspberry Pi

### SSH Access

Connect to the Raspberry Pi from your development machine:

```bash
ssh yehudalevavi@room-guard
```

> If `room-guard` doesn't resolve, try `room-guard.local` or the Pi's IP address.

### Project location on the Pi

The application is deployed at:

```
/home/yehudalevavi/rpiProject/
```

### Quick debug workflow

```bash
ssh yehudalevavi@room-guard
cd ~/rpiProject
source .venv/bin/activate
python3 src/room_guard.py
```

### View service logs

```bash
ssh yehudalevavi@room-guard "journalctl -u room_guard -f"
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Can't SSH to `room-guard` | Check Wi-Fi credentials, try `room-guard.local` or the IP address instead |
| PIR sensor always HIGH | Wait 30–60s after powering on (calibration period). Adjust sensitivity pot. |
| PIR sensor never triggers | Check wiring (VCC to 5V, not 3.3V). Try adjusting sensitivity clockwise. |
| LED doesn't light | Check polarity (long leg = +). Verify resistor connection. |
| Buzzer doesn't sound | Check polarity (+ to GPIO). Some buzzers have a tiny sticker on top — remove it. |
| `Permission denied` on GPIO | Run `sudo usermod -aG gpio $USER` and re-login. Or run with `sudo`. |
| `lgpio` import error in venv | Recreate venv with `python3 -m venv --system-site-packages .venv` |
| DHT11 reads all fail | Check DATA wire is on Pin 7 (GPIO 4). Ensure VCC is on 5V. Install `libgpiod2`: `sudo apt install -y libgpiod2` |
| DHT11 reads are flaky | Normal — the DHT11 fails ~10-20% of reads. The sensor module retries automatically. |
| Service won't start | Check `journalctl -u room_guard -e` for errors. Verify file paths in .service file. |
