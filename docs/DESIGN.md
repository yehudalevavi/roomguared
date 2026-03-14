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
| 7 | Passive buzzer         | 1   | ~$1         | 3V–5V, **no** white sticker on top (unlike active buzzer) |
| 8 | LCD1602 display        | 1   | ~$3         | 16×2 character LCD, HD44780 controller  |
| 9 | 10KΩ potentiometer     | 1   | ~$0.50      | For LCD contrast adjustment             |
| 10 | Breadboard             | 1   | ~$3         | Half-size or full-size                  |
| 11 | Jumper wires (Male-to-Female) | ~20 | ~$2  | For connecting RPi GPIO to breadboard  |
| 12 | IR receiver (VS1838B)  | 1   | ~$1         | 3-pin: Signal, VCC, GND (from Elegoo kit) |
| 13 | IR remote control      | 1   | —           | NEC protocol remote (from Elegoo kit or any NEC remote) |
| 14 | MFRC522 NFC/RFID reader | 1  | ~$2         | SPI interface, 3.3V — **do not power from 5V** |
| 15 | NFC cards / key fobs   | 1+  | ~$1         | 13.56 MHz MIFARE tags (included with MFRC522 kits) |
| 16 | Bluetooth speaker (JBL Flip 7) | 1 | ~$130 | A2DP audio output — any BT speaker works |

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
| Buzzer (+)       | GPIO 22   | Pin 15      | PWM OUTPUT |
| DHT11 DATA       | GPIO 4    | Pin 7       | INPUT     |
| IR Receiver      | GPIO 18   | Pin 12      | INPUT     |
| LCD RS           | GPIO 26   | Pin 37      | OUTPUT    |
| LCD E            | GPIO 19   | Pin 35      | OUTPUT    |
| LCD D4           | GPIO 13   | Pin 33      | OUTPUT    |
| LCD D5           | GPIO 6    | Pin 31      | OUTPUT    |
| LCD D6           | GPIO 5    | Pin 29      | OUTPUT    |
| LCD D7           | GPIO 12   | Pin 32      | OUTPUT     |
| NFC SDA (CE0)    | GPIO 8    | Pin 24      | SPI        |
| NFC SCK          | GPIO 11   | Pin 23      | SPI        |
| NFC MOSI         | GPIO 10   | Pin 19      | SPI        |
| NFC MISO         | GPIO 9    | Pin 21      | SPI        |
| NFC RST          | GPIO 25   | Pin 22      | OUTPUT     |

> All component VCC pins connect to the breadboard **+ rail**, and all GND pins to the **− rail** — **except** the MFRC522 NFC reader, which connects directly to RPi Pin 17 (3.3V) and Pin 20 (GND).

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
                  └─────────────────────── IR Receiver Signal (yellow wire)
         ┌──────────────────────────────── LED Anode (+) via 220Ω resistor
  GPIO27 (13)(14) GND
         ┌──────────────────────────────── Buzzer (+)
  GPIO22 (15)(16) GPIO23
         ┌──────────────────────────────── NFC 3.3V (direct to module — NOT 5V!)
    3V3  (17)(18) GPIO24
         ┌──────────────────────────────── NFC MOSI
  GPIO10 (19)(20) GND
                  └─────────────────────── NFC GND (direct to module)
         ┌──────────────────────────────── NFC MISO
   GPIO9 (21)(22) GPIO25
                  └─────────────────────── NFC RST
         ┌──────────────────────────────── NFC SCK (SPI clock)
  GPIO11 (23)(24) GPIO8
                  └─────────────────────── NFC SDA (SPI CE0)
    GND  (25)(26) GPIO7
   GPIO0 (27)(28) GPIO1
         ┌──────────────────────────────── LCD D6
   GPIO5 (29)(30) GND
         ┌──────────────────────────────── LCD D5
   GPIO6 (31)(32) GPIO12
                  └─────────────────────── LCD D7 (moved from Pin 23 for NFC)
         ┌──────────────────────────────── LCD D4
  GPIO13 (33)(34) GND
         ┌──────────────────────────────── LCD Enable (E)
  GPIO19 (35)(36) GPIO16
         ┌──────────────────────────────── LCD Register Select (RS)
  GPIO26 (37)(38) GPIO20
    GND  (39)(40) GPIO21


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
    │                                               │
    │  IR Receiver VCC ── RPi Pin 1 (3.3V)            │
    │  IR Receiver GND ── − rail                     │
    │                                               │
    │  LCD VSS (pin 1) ──── − rail (GND)            │
    │  LCD VDD (pin 2) ──── + rail (5V)             │
    │  LCD V0  (pin 3) ──── Potentiometer wiper     │
    │  LCD RW  (pin 5) ──── − rail (GND)            │
    │  LCD A   (pin 15) ─── + rail via 220Ω         │
    │  LCD K   (pin 16) ─── − rail (GND)            │
    │                                               │
    │  Potentiometer:                               │
    │    Left leg  ──── + rail (5V)                  │
    │    Right leg ──── − rail (GND)                 │
    │    Middle leg ─── LCD V0 (pin 3)               │
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

#### Passive Buzzer
1. Place the passive buzzer on the breadboard.
   > The passive buzzer is slightly larger than the active one and has **no** white sticker/marking on top.
2. Connect the buzzer's **(+) pin** to **Pin 15 (GPIO 22)**.
3. Connect the buzzer's **(−) pin** to the breadboard **− rail**.

#### DHT11 Temperature & Humidity Sensor
1. The DHT11 module (from the Elegoo kit) has 3 pins labeled **+**, **out**, and **−**.
2. Connect **+** (VCC) to the breadboard **+ rail**.
3. Connect **out** (DATA) to **Pin 7 (GPIO 4)** using a yellow/green jumper wire.
4. Connect **−** (GND) to the breadboard **− rail**.

> The Elegoo DHT11 module has a built-in 10KΩ pull-up resistor — no extra resistor needed.

#### IR Receiver (VS1838B)
1. The IR receiver module has 3 pins. With the dome (rounded side) facing you: **Signal** (left), **GND** (middle), **VCC** (right). ⚠️ Pin order varies by module — check the labels or datasheet.
2. Connect **VCC** to RPi **Pin 1 (3.3V)** — **not** the 5V breadboard rail (see warning below).
3. Connect **Signal** to **Pin 12 (GPIO 18)** using a yellow/green jumper wire.
4. Connect **GND** to the breadboard **− rail**.

> ⚠️ **Power the IR receiver from 3.3V, not 5V.** The signal pin connects directly to GPIO 18, and RPi GPIOs are 3.3V only. The VS1838B works fine at 3.3V (rated 2.7–5.5V). Powering from 5V would risk sending 5V into the GPIO pin and damaging the Pi.

#### LCD1602 Display (4-bit parallel mode)

The LCD1602 has **16 pins** along the top edge. We use 4-bit mode so only 6 GPIO wires are needed (RS, E, D4–D7). The rest are power, ground, and contrast.

**LCD pin connections:**

| LCD Pin | LCD Label | Connect To | Notes |
|---------|-----------|-----------|-------|
| 1 | VSS | Breadboard − rail | Ground |
| 2 | VDD | Breadboard + rail | 5V Power |
| 3 | V0 | Potentiometer wiper (middle leg) | Contrast adjustment |
| 4 | RS | RPi Pin 37 (GPIO 26) | Register Select |
| 5 | RW | Breadboard − rail | Ground = Write mode (always) |
| 6 | E | RPi Pin 35 (GPIO 19) | Enable |
| 7 | D0 | — | Not connected (4-bit mode) |
| 8 | D1 | — | Not connected (4-bit mode) |
| 9 | D2 | — | Not connected (4-bit mode) |
| 10 | D3 | — | Not connected (4-bit mode) |
| 11 | D4 | RPi Pin 33 (GPIO 13) | Data bit 4 |
| 12 | D5 | RPi Pin 31 (GPIO 6) | Data bit 5 |
| 13 | D6 | RPi Pin 29 (GPIO 5) | Data bit 6 |
| 14 | D7 | RPi Pin 32 (GPIO 12) | Data bit 7 *(reassigned from GPIO 11 for NFC SPI)* |
| 15 | A | Breadboard + rail via 220Ω resistor | Backlight anode (+) |
| 16 | K | Breadboard − rail | Backlight cathode (−) |

> The 220Ω resistor on pin 15 (A) limits current to the backlight LED. Without it, you may damage the backlight.

**Potentiometer wiring (for contrast adjustment):**

| Potentiometer Pin | Connect To |
|-------------------|-----------|
| Left leg | Breadboard + rail (5V) |
| Right leg | Breadboard − rail (GND) |
| Middle leg (wiper) | LCD Pin 3 (V0) |

**Step-by-step:**

1. Place the LCD1602 on the breadboard (it spans many rows).
2. Wire LCD **pin 1 (VSS)** to the breadboard **− rail**.
3. Wire LCD **pin 2 (VDD)** to the breadboard **+ rail**.
4. Place the **10KΩ potentiometer** on the breadboard.
   - Left leg → **+ rail**, Right leg → **− rail**, Middle leg → LCD **pin 3 (V0)**.
5. Wire LCD **pin 4 (RS)** to RPi **Pin 37 (GPIO 26)**.
6. Wire LCD **pin 5 (RW)** to the breadboard **− rail** (ground = write mode).
7. Wire LCD **pin 6 (E)** to RPi **Pin 35 (GPIO 19)**.
8. Leave LCD pins 7–10 (D0–D3) **unconnected**.
9. Wire LCD **pin 11 (D4)** to RPi **Pin 33 (GPIO 13)**.
10. Wire LCD **pin 12 (D5)** to RPi **Pin 31 (GPIO 6)**.
11. Wire LCD **pin 13 (D6)** to RPi **Pin 29 (GPIO 5)**.
12. Wire LCD **pin 14 (D7)** to RPi **Pin 32 (GPIO 12)**.
13. Wire a **220Ω resistor** from the breadboard **+ rail** to LCD **pin 15 (A)** (backlight power).
14. Wire LCD **pin 16 (K)** to the breadboard **− rail**.

> 💡 After powering on, slowly turn the potentiometer knob until you see solid rectangles on the top row of the LCD — that means contrast is set correctly.

##### Testing the LCD

After wiring, run the hardware test:

```bash
source .venv/bin/activate
python3 src/test_lcd.py
```

You should see "Hello Room Guard!" on the first line and "LCD Working!" on the second. The test cycles through several text patterns. If the backlight is on but no text is visible, adjust the potentiometer. If the text looks garbled, double-check the D4–D7 data wires.

##### Testing the DHT11

After wiring, run the hardware test:

```bash
source .venv/bin/activate
python3 src/test_dht11.py
```

You should see 10 readings with temperature (°C) and humidity (%). At least 8/10 should succeed. If not, check the [Troubleshooting](#troubleshooting) section.

#### MFRC522 NFC/RFID Reader (SPI)

The MFRC522 module uses SPI (Serial Peripheral Interface) to communicate with the Pi. It connects to the Pi's dedicated SPI0 pins.

> ⚠️ **Before wiring:** SPI must be enabled on the Pi. Run `sudo raspi-config nonint do_spi 0` and reboot.

> ⚠️ **Power from 3.3V, not 5V!** The MFRC522 operates at 3.3V logic. Its SPI pins connect directly to RPi GPIOs which are 3.3V-only — powering from 5V risks damaging the Pi.

> ⚠️ **GPIO 11 conflict:** GPIO 11 (Pin 23) was previously used for LCD D7. It has been reassigned to the NFC SPI clock (SCK). LCD D7 has been moved to GPIO 12 (Pin 32). If your LCD is already wired, **move the D7 wire from Pin 23 to Pin 32** before adding the NFC reader.

**MFRC522 pin connections:**

| MFRC522 Pin | Connect To | Notes |
|-------------|-----------|-------|
| SDA | RPi Pin 24 (GPIO 8) | SPI chip select (CE0) |
| SCK | RPi Pin 23 (GPIO 11) | SPI clock |
| MOSI | RPi Pin 19 (GPIO 10) | SPI data out (Pi → reader) |
| MISO | RPi Pin 21 (GPIO 9) | SPI data in (reader → Pi) |
| RST | RPi Pin 22 (GPIO 25) | Reset |
| 3.3V | RPi Pin 17 (3.3V) | ⚠️ Must use 3.3V, not 5V |
| GND | RPi Pin 20 (GND) | Ground (direct to Pi) |
| IRQ | — | Not connected (not needed) |

**Step-by-step:**

1. If LCD D7 is currently wired to Pin 23 (GPIO 11), **move it to Pin 32 (GPIO 12)**.
2. Wire MFRC522 **SDA** to RPi **Pin 24 (GPIO 8)**.
3. Wire MFRC522 **SCK** to RPi **Pin 23 (GPIO 11)**.
4. Wire MFRC522 **MOSI** to RPi **Pin 19 (GPIO 10)**.
5. Wire MFRC522 **MISO** to RPi **Pin 21 (GPIO 9)**.
6. Wire MFRC522 **RST** to RPi **Pin 22 (GPIO 25)**.
7. Wire MFRC522 **3.3V** to RPi **Pin 17 (3.3V)** — **not** the 5V breadboard rail.
8. Wire MFRC522 **GND** to RPi **Pin 20 (GND)**.
9. Leave MFRC522 **IRQ** not connected.

##### Testing the NFC Reader

First, verify SPI is enabled:

```bash
ls /dev/spidev*
```

Should show `/dev/spidev0.0` and `/dev/spidev0.1`. If not, enable SPI and reboot (see above).

Then run the hardware test:

```bash
source .venv/bin/activate
python3 src/test_nfc.py
```

Hold an NFC card or key fob near the reader. You should see the card's UID printed. Press Ctrl+C to stop. Use the printed UIDs to register cards via the web dashboard (💳 NFC Cards section).

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

Before running the full application, verify that the LED and passive buzzer are wired correctly:

```bash
source .venv/bin/activate
python3 src/test_outputs.py   # LED on/off test
python3 src/test_buzzer.py    # Passive buzzer melody test
```

The buzzer test plays 4 system melodies (startup, arm, sensor error, disarm) plus 3 random samples from the 20-melody motion library. If you hear clicking instead of tones, you may have the active buzzer connected — swap it for the passive one.

If the LED doesn't light up or the buzzer doesn't sound, check the [Troubleshooting](#troubleshooting) section.

### Run manually

There are two ways to run the Room Guard:

**Option A — Web Dashboard (recommended):**

```bash
source .venv/bin/activate
python3 src/web_app.py
```

Then open **`http://room-guard:5000`** in your browser (phone or laptop). The dashboard lets you arm/disarm the sensor, toggle the LED, play melodies, and view the activity log — all from a web interface.

**Option B — Standalone CLI (no web UI):**

```bash
source .venv/bin/activate
python3 src/room_guard.py
```

You should see:

```
[Room Guard] Starting up...
[Room Guard] PIR sensor on GPIO 17
[Room Guard] LED on GPIO 27
[Room Guard] Passive buzzer on GPIO 22
[Room Guard] 20 melodies loaded, 10s cooldown
[Room Guard] Waiting for motion...
```

Wave your hand in front of the PIR sensor. You should see:

```
[Room Guard] 2026-03-11 09:30:05 — MOTION DETECTED! Playing: Eine kleine Nachtmusik
```

Each detection plays a different random melody from the library of 20 famous tunes.

Press **Ctrl+C** to stop (plays a descending disarm melody).

---

## Step 5 — Auto-Start on Boot

The systemd service runs the **web dashboard** (`web_app.py`), which includes all Room Guard functionality and makes the dashboard available at `http://room-guard:5000` on boot.

The service also **auto-updates** on every start — it runs `git pull` and `pip install` before launching the app, so the Pi always runs the latest code from GitHub. If the network is unavailable, the update is skipped gracefully and the app starts with the existing code.

### Install the systemd service

```bash
sudo cp config/room_guard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable room_guard
sudo systemctl start room_guard
```

### Deploy new code (no SSH needed)

Just push to the `master` branch on GitHub, then reboot the Pi or run:

```bash
sudo systemctl restart room_guard
```

The service will pull the latest code and restart the app automatically.

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
Browser (phone/laptop)           Raspberry Pi
┌──────────────┐     HTTP       ┌──────────────────────────────────┐
│  Dashboard   │◄──────────────►│  Flask web_app.py (port 5000)   │
│  index.html  │   local net    │         │                        │
└──────────────┘                │   RoomGuard class                │
                                │   (room_guard.py)                │
IR Remote Control               │    ├── PIR sensor (GPIO 17)      │
┌──────────────┐     IR signal  │    ├── LED (GPIO 27)             │
│  🎮 Remote   │───────────────►│    ├── Buzzer (GPIO 22)          │
│   (NEC)      │   GPIO 18     │    ├── IR receiver (GPIO 18)     │
└──────────────┘                │    ├── LCD 16×2 (GPIO 26,19,     │
                                │    │   13,6,5,12)                 │
NFC Cards / Key Fobs            │    ├── NFC reader MFRC522 (SPI0: │
┌──────────────┐     13.56 MHz  │    │   GPIO 8,11,10,9,25)        │
│  💳 Card     │───────────────►│    ├── Melody library (20 tunes) │
│  (MIFARE)    │   MFRC522     │    ├── BluetoothSpeaker (BlueZ)  │
└──────────────┘                │    └── SpotifyPlayer (spotipy)   │
                                │                                   │
Bluetooth Speaker               │   spotifyd (Spotify Connect)     │
┌──────────────┐     A2DP      │    └── PulseAudio audio sink     │
│  🔊 JBL     │◄───────────────│                                   │
│  Flip 7      │   Bluetooth   │   Spotify Cloud ──► spotifyd     │
└──────────────┘                └──────────────────────────────────┘
```

### Components

- **`src/web_app.py`** — Flask web application. Serves the dashboard HTML and a REST API for controlling the system. Binds to `0.0.0.0:5000`. Hardware initializes in a background thread so the dashboard is available immediately (PIR needs 40s to calibrate).
- **`src/room_guard.py`** — `RoomGuard` class that manages all hardware (PIR, LED, buzzer) and application state (armed/disarmed, motion count, event log). Thread-safe — all state is protected with a lock since Flask serves from multiple threads and gpiozero callbacks run in their own thread. Can also run standalone as a CLI app (`python3 src/room_guard.py`).
- **`src/lcd_display.py`** — LCD1602 driver using RPLCD in 4-bit GPIO mode. Provides `LCDDisplay` class with `write(line1, line2)` for updating text, `clear()`, and a change-detection cache that only rewrites lines when their content changes (reducing flicker). Truncates and pads text to 16 characters automatically.
- **`src/buzzer.py`** — PWM buzzer driver with a full chromatic scale (C4–C6). Provides system melodies (startup, arm, disarm, sensor error) and the `Buzzer` class for playing tones and melodies.
- **`src/melody_library.py`** — Library of 20 famous public-domain melodies. `get_random_melody()` returns a random melody for motion alerts.
- **`src/ir_remote.py`** — IR remote control handler using Linux `gpio-ir-recv` overlay and `evdev`. Listens for NEC remote keypresses in a background thread and dispatches actions (prev/play-pause/next melody, arm/disarm) to the `RoomGuard` instance. Button mapping is configurable.
- **`src/nfc_reader.py`** — NFC/RFID card reader using the MFRC522 module via SPI. Polls for cards in a background thread, dispatches configurable actions (arm/disarm, LED toggle, play melody, etc.) to the `RoomGuard` instance. Card-to-action mappings stored in `config/nfc_cards.json`. 2-second debounce prevents repeat triggers.
- **`src/templates/index.html`** — Single-page responsive dashboard. Dark theme, mobile-friendly, no CDN dependencies (works offline on local network). Auto-refreshes status (3s) and logs (5s) via `fetch` API.

### Web Dashboard

The dashboard is accessible at `http://room-guard:5000` from any device on the local network.

**Dashboard controls:**
- **Motion Sensor** — Toggle button to arm/disarm. Shows armed state with a status badge (● Armed / ○ Disarmed / 🎵 Playing).
- **LED** — Toggle button to turn on/off. Badge shows current state.
- **Play Melody** — Dropdown of all 20 melodies + play button. Plays the selected melody on the buzzer.
- **Status** — Motion count and last event time (auto-refreshes every 3 seconds).
- **Activity Log** — Scrollable log of recent events including motion detections with melody names (auto-refreshes every 5 seconds).

**REST API endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard HTML page |
| GET | `/api/status` | JSON: armed, motion count, last event, LED state, playing |
| POST | `/api/arm` | Enable motion detection |
| POST | `/api/disarm` | Disable motion detection |
| POST | `/api/led/on` | Turn LED on |
| POST | `/api/led/off` | Turn LED off |
| POST | `/api/play/<name>` | Play a specific melody by name |
| GET | `/api/melodies` | List all 20 available melody names |
| GET | `/api/logs?limit=50` | Recent activity log entries (JSON) |

### How it works

1. **Startup**: `web_app.py` creates a `RoomGuard` instance and starts Flask on port 5000. Hardware initialization (GPIO setup + PIR calibration) runs in a background daemon thread so the dashboard is immediately available.
2. **Calibration**: The PIR sensor requires ~40 seconds to calibrate. During this time, the dashboard is accessible and shows status, but motion detection is not yet armed.
3. **Auto-arm**: After calibration completes, the system automatically arms the motion sensor.
4. **Motion detected**: The PIR callback fires — a random melody is selected from the 20-melody library. The LED turns on, the melody plays via PWM, and the event (with melody name) is logged.
5. **Cooldown**: After the configured cooldown period (default 10s), the system returns to watching for the next motion.
6. **Dashboard control**: Users can arm/disarm, toggle the LED, and play melodies on demand via the web UI at any time. All controls respond immediately.
7. **Shutdown**: On SIGINT or SIGTERM (systemd stop), all GPIO pins are cleaned up gracefully.

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
sudo systemctl stop room_guard   # Stop the service first
source .venv/bin/activate
python3 src/web_app.py           # Run interactively (Ctrl+C to stop)
```

Or for CLI-only debugging (no web UI):

```bash
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
| Buzzer doesn't sound | Check polarity (+ to GPIO). Ensure you have the **passive** buzzer (no white sticker on top). |
| Buzzer clicks instead of tones | You may have the **active** buzzer connected. Swap it for the passive one. |
| `Permission denied` on GPIO | Run `sudo usermod -aG gpio $USER` and re-login. Or run with `sudo`. |
| `lgpio` import error in venv | Recreate venv with `python3 -m venv --system-site-packages .venv` |
| DHT11 reads all fail | Check DATA wire is on Pin 7 (GPIO 4). Ensure VCC is on 5V. Install `libgpiod2`: `sudo apt install -y libgpiod2` |
| DHT11 reads are flaky | Normal — the DHT11 fails ~10-20% of reads. The sensor module retries automatically. |
| Service won't start | Check `journalctl -u room_guard -e` for errors. Verify file paths in .service file. |
| Dashboard won't load | Verify the service is running: `sudo systemctl status room_guard`. Check port 5000 is not blocked. Try `http://<Pi-IP>:5000` if hostname doesn't resolve. |
| LCD backlight on but no text | Adjust the potentiometer slowly until text appears. The contrast must be tuned. |
| LCD shows garbled/random characters | Double-check D4-D7 data wires match GPIO 13, 6, 5, 11 respectively. Verify RS (GPIO 26) and E (GPIO 19). |
| LCD not lighting up at all | Check 220Ω resistor from + rail to LCD pin 15 (A). Verify VDD (pin 2) is on + rail and VSS (pin 1) on − rail. |
| Dashboard shows "Disarmed" after boot | Normal — the PIR sensor needs ~40 seconds to calibrate, then it auto-arms. Refresh the page after a minute. |
| IR remote not responding | Verify `dtoverlay=gpio-ir,gpio_pin=18` is in `/boot/config.txt` and you've rebooted. Run `ir-keytable` to check the device is detected. |
| IR receiver picks up no signals | Check wiring — Signal pin to GPIO 18, VCC to 5V, GND to GND. Point the remote directly at the receiver dome. Try `ir-keytable -t` to watch for raw events. |
| IR buttons trigger wrong actions | Run `src/test_ir.py` to see the key codes your remote sends, then update the button mapping in `ir_remote.py`. |
