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
9. [Troubleshooting](#troubleshooting)

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
   - ☑️ Set hostname: `roomguard`
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
ssh pi@roomguard.local
```

> If `roomguard.local` doesn't work, find the Pi's IP address from your router's admin page and use `ssh pi@<IP_ADDRESS>`.

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

### GPIO Pin Assignments (BCM Numbering)

| Component        | GPIO Pin  | Physical Pin | Direction |
|------------------|-----------|-------------|-----------|
| PIR Sensor OUT   | GPIO 17   | Pin 11      | INPUT     |
| PIR Sensor VCC   | —         | Pin 2 (5V)  | POWER     |
| PIR Sensor GND   | —         | Pin 6 (GND) | GROUND    |
| LED (+) via 220Ω | GPIO 27   | Pin 13      | OUTPUT    |
| LED (−)          | —         | Pin 14 (GND)| GROUND    |
| Buzzer (+)       | GPIO 22   | Pin 15      | OUTPUT    |
| Buzzer (−)       | —         | Pin 9 (GND) | GROUND    |

### Wiring Diagram

```
    Raspberry Pi 4 GPIO Header
    (Pin 1 = top-left, Pin 2 = top-right)

    3V3  (1) (2)  5V ─────────────────── PIR VCC (red wire)
  GPIO2  (3) (4)  5V
  GPIO3  (5) (6)  GND ────────────────── PIR GND (black wire)
  GPIO4  (7) (8)  GPIO14
    GND  (9) (10) GPIO15
         ┌──────────────────────────────── PIR OUT (yellow wire)
  GPIO17 (11)(12) GPIO18
         ┌──────────────────────────────── LED Anode (+) via 220Ω resistor
  GPIO27 (13)(14) GND ────────────────── LED Cathode (−)
         ┌──────────────────────────────── Buzzer (+)
  GPIO22 (15)(16) GPIO23
    3V3  (17)(18) GPIO24
```

### Step-by-Step Wiring

> ⚠️ **Always wire with the Raspberry Pi powered OFF!**

#### PIR Sensor (HC-SR501)
1. Connect **VCC** (usually the left pin, marked +) to **Pin 2 (5V)** using a red jumper wire.
2. Connect **OUT** (middle pin) to **Pin 11 (GPIO 17)** using a yellow/green jumper wire.
3. Connect **GND** (right pin, marked −) to **Pin 6 (GND)** using a black jumper wire.

#### LED
1. Place the LED on the breadboard.
2. Connect a **220Ω resistor** from **Pin 13 (GPIO 27)** to the LED's **long leg (anode, +)**.
3. Connect the LED's **short leg (cathode, −)** to **Pin 14 (GND)**.

#### Active Buzzer
1. Place the buzzer on the breadboard.
2. Connect the buzzer's **(+) pin** to **Pin 15 (GPIO 22)**.
3. Connect the buzzer's **(−) pin** to **Pin 9 (GND)**.

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
scp -r src/ config/ requirements.txt pi@roomguard.local:~/rpiProject/
```

### Install dependencies

```bash
cd ~/rpiProject
pip3 install -r requirements.txt
```

### Run manually

```bash
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

1. **Initialization**: Set up GPIO pins (input for PIR, output for LED + buzzer). Register edge-detection callback on the PIR pin.
2. **Waiting**: The main thread sleeps while the GPIO library watches for a RISING edge on GPIO 17.
3. **Motion detected**: The callback fires — LED and buzzer are turned ON. A timestamp is logged.
4. **Cooldown**: After the configured cooldown period (default 5s), LED and buzzer are turned OFF.
5. **Repeat**: System returns to waiting state.
6. **Shutdown**: On SIGINT (Ctrl+C) or SIGTERM (systemd stop), all GPIO pins are cleaned up.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Can't SSH to `roomguard.local` | Check Wi-Fi credentials, try the IP address instead |
| PIR sensor always HIGH | Wait 30–60s after powering on (calibration period). Adjust sensitivity pot. |
| PIR sensor never triggers | Check wiring (VCC to 5V, not 3.3V). Try adjusting sensitivity clockwise. |
| LED doesn't light | Check polarity (long leg = +). Verify resistor connection. |
| Buzzer doesn't sound | Check polarity (+ to GPIO). Some buzzers have a tiny sticker on top — remove it. |
| `Permission denied` on GPIO | Run `sudo usermod -aG gpio $USER` and re-login. Or run with `sudo`. |
| Service won't start | Check `journalctl -u room_guard -e` for errors. Verify file paths in .service file. |
