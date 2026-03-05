# 🌡️ Smart Room Dashboard — Implementation Plan

> Evolving the Room Guard into a room monitoring station with temperature, humidity, LCD display, RTC clock, and data logging.

## Approach

Build incrementally — one component at a time. Each phase adds one new hardware piece with its own test script, so you can validate wiring before moving on. The final phase integrates everything into the existing Room Guard.

## Existing Setup (already working)

| Component | GPIO (BCM) | Physical Pin |
|-----------|-----------|-------------|
| PIR Sensor OUT | GPIO 17 | Pin 11 |
| LED (+) | GPIO 27 | Pin 13 |
| Buzzer (+) | GPIO 22 | Pin 15 |

---

## Phase 1: DHT11 Temperature & Humidity Sensor

**Goal:** Read temperature and humidity, print to console.

**New wiring (3 wires):**

| Wire | From | To |
|------|------|----|
| VCC (red) | DHT11 `+` pin | RPi Pin 2 (5V) |
| DATA (yellow) | DHT11 `out` pin | RPi Pin 7 (GPIO 4) |
| GND (black) | DHT11 `-` pin | RPi Pin 9 (GND) |

> The DHT11 module on the Elegoo kit has a built-in pull-up resistor, so no extra resistor needed.

**Software:**
- Install `adafruit-circuitpython-dht` library
- Create `src/test_dht11.py` — reads and prints temperature (°C) and humidity (%) every 2 seconds
- Run for 10 readings, then exit

**Validation:**
- ✅ Temperature shows a reasonable value (15–35°C indoors)
- ✅ Humidity shows a reasonable value (20–80%)
- ✅ No read errors for at least 8 out of 10 readings

---

## Phase 2: LCD1602 Display (4-bit parallel mode)

**Goal:** Display text on the LCD screen.

**New wiring (12 wires + potentiometer):**

The LCD1602 has 16 pins along the top. Wire them as follows:

| LCD Pin | LCD Label | Connect To | Notes |
|---------|-----------|-----------|-------|
| 1 | VSS | RPi Pin 6 (GND) | Ground |
| 2 | VDD | RPi Pin 2 (5V) | Power |
| 3 | V0 | Potentiometer wiper | Contrast adjustment |
| 4 | RS | RPi Pin 37 (GPIO 26) | Register Select |
| 5 | RW | RPi Pin 6 (GND) | Ground = Write mode |
| 6 | E | RPi Pin 35 (GPIO 19) | Enable |
| 7 | D0 | — | Not connected |
| 8 | D1 | — | Not connected |
| 9 | D2 | — | Not connected |
| 10 | D3 | — | Not connected |
| 11 | D4 | RPi Pin 33 (GPIO 13) | Data bit 4 |
| 12 | D5 | RPi Pin 31 (GPIO 6) | Data bit 5 |
| 13 | D6 | RPi Pin 29 (GPIO 5) | Data bit 6 |
| 14 | D7 | RPi Pin 23 (GPIO 11) | Data bit 7 |
| 15 | A | RPi Pin 2 (5V) via 220Ω | Backlight + |
| 16 | K | RPi Pin 6 (GND) | Backlight − |

**Potentiometer wiring (for contrast):**

| Potentiometer Pin | Connect To |
|-------------------|-----------|
| Left leg | RPi Pin 2 (5V) |
| Right leg | RPi Pin 6 (GND) |
| Middle leg (wiper) | LCD Pin 3 (V0) |

> After powering on, slowly turn the potentiometer until you see solid rectangles on the LCD top row — that means contrast is correct.

**Software:**
- Install `RPLCD` library
- Create `src/test_lcd.py` — displays "Hello Room Guard!" on line 1 and "LCD Working!" on line 2
- Test clearing the screen and writing new text

**Validation:**
- ✅ LCD backlight turns on when powered
- ✅ Turning potentiometer shows/hides block characters (contrast works)
- ✅ "Hello Room Guard!" appears clearly on line 1
- ✅ Text can be updated without artifacts

---

## Phase 3: DHT11 + LCD Integration

**Goal:** Show live temperature and humidity on the LCD.

**New wiring:** None — uses Phase 1 + Phase 2 wiring.

**Software:**
- Create `src/test_dht_lcd.py` — reads DHT11 and displays on LCD:
  - Line 1: `Temp: 23.0 C`
  - Line 2: `Humidity: 45.0%`
- Updates every 5 seconds
- Handles DHT11 read errors gracefully (shows last good reading)

**Validation:**
- ✅ LCD shows temperature and humidity
- ✅ Values update every 5 seconds
- ✅ Breathing on the sensor changes humidity reading
- ✅ No crashes on occasional DHT11 read errors

---

## Phase 4: DS1307 RTC Module (Real-Time Clock)

**Goal:** Get accurate timestamps even without internet.

**New wiring (4 wires):**

| Wire | From | To |
|------|------|----|
| VCC (red) | DS1307 VCC | RPi Pin 1 (3.3V) |
| GND (black) | DS1307 GND | RPi Pin 14 (GND) |
| SDA (blue) | DS1307 SDA | RPi Pin 3 (GPIO 2 / SDA1) |
| SCL (yellow) | DS1307 SCL | RPi Pin 5 (GPIO 3 / SCL1) |

> ⚠️ Must enable I2C on the Raspberry Pi first (see software steps).

**Software:**
- Enable I2C: `sudo raspi-config` → Interface Options → I2C → Enable
- Install `i2c-tools` and verify: `sudo i2cdetect -y 1` (should show device at address `0x68`)
- Create `src/test_rtc.py` — sets the RTC time from system clock, then reads it back every second for 10 seconds

**Validation:**
- ✅ `i2cdetect` shows a device at address `0x68`
- ✅ RTC time matches system time (within 1-2 seconds)
- ✅ After unplugging RPi and repowering, RTC still keeps time (if battery is inserted)

---

## Phase 5: Smart Room Dashboard (Full Integration)

**Goal:** Merge all components into an upgraded `room_guard.py`.

**New wiring:** None — all wired in previous phases.

**Software — new features:**
- LCD screen cycles between pages (every 5 seconds):
  - Page 1: `Temp: 23.0C` / `Humidity: 45%`
  - Page 2: `Motion: 7 today` / `Last: 14:23:05`
  - Page 3: `Room Guard ON` / `<current date/time>`
- Motion events are timestamped using the RTC
- Motion events are logged to `~/rpiProject/logs/events.csv`:
  ```
  datetime,temperature,humidity,event
  2026-03-05 14:23:05,23.0,45.0,motion_detected
  ```
- Existing Room Guard behavior (LED + buzzer alert) is preserved
- Update `requirements.txt` with new dependencies
- Update `DESIGN.md` with new wiring diagram and architecture

**Validation:**
- ✅ All original Room Guard functionality still works (PIR → LED + buzzer)
- ✅ LCD shows cycling pages with real sensor data
- ✅ Motion events appear in `logs/events.csv` with correct timestamps
- ✅ System runs stable for 10+ minutes
- ✅ Service can be restarted and picks up cleanly

---

## Phase 6: Passive Buzzer with Melodies & Sound Cues

**Goal:** Replace the active buzzer with the passive buzzer to play real melodies and distinct audio cues for different events.

**Why:** The active buzzer can only make one tone (on/off). The passive buzzer can play any frequency, enabling recognizable melodies for the alarm and short sound cues for other system events.

**New wiring (swap 1 wire):**

| Change | From | To |
|--------|------|----|
| Disconnect active buzzer from GPIO 22 | Active buzzer (+) | — |
| Connect passive buzzer to GPIO 22 | Passive buzzer (+) | RPi Pin 15 (GPIO 22) |
| Connect passive buzzer GND | Passive buzzer (−) | RPi Pin 9 (GND) |

> Same pin (GPIO 22), just swap the buzzer component. The passive buzzer is slightly larger and has **no** white sticker/marking on top (unlike the active buzzer which has one).

**Software:**
- Create `src/buzzer.py` — a reusable buzzer module with:
  - `play_tone(frequency, duration)` — play a single tone using PWM
  - `play_melody(notes)` — play a sequence of (frequency, duration) tuples
  - Predefined melodies:
    - `MELODY_ALARM` — urgent siren pattern for motion detection
    - `MELODY_STARTUP` — friendly ascending jingle on boot
    - `MELODY_ARM` — short confirmation beep when system starts watching
    - `MELODY_DISARM` — descending tone when system stops (Ctrl+C / service stop)
    - `MELODY_SENSOR_ERROR` — low double-beep when a sensor read fails
- Create `src/test_buzzer.py` — hardware test that plays each melody in sequence
- Create `tests/test_buzzer_unit.py` — unit tests for tone/melody logic
- Update `room_guard.py` to use the new buzzer module:
  - Motion detected → `MELODY_ALARM`
  - Startup complete → `MELODY_STARTUP`
  - Shutdown → `MELODY_DISARM`
  - DHT11/RTC read failure → `MELODY_SENSOR_ERROR` (if dashboard is integrated)

**Validation:**
- ✅ Each melody plays distinctly and is easy to tell apart
- ✅ Tones sound at correct pitch (not just clicking)
- ✅ Motion alert melody is noticeably urgent vs. friendly startup jingle
- ✅ Existing LED behavior is unaffected
- ✅ Unit tests pass without hardware

---

## Phase 7 (Optional/Bonus): Photoresistor Light Level

**Goal:** Add light level sensing to the dashboard.

**Note:** The RPi has no analog inputs. This uses a capacitor timing trick (RC circuit) to estimate light level. This is approximate but fun.

**New wiring:**
- Photoresistor + 1µF capacitor in an RC circuit on one GPIO pin
- Details TBD based on available capacitor values in the kit

**This phase is optional** — skip it if you want to keep things simple.

---

## GPIO Pin Map (Final)

| Component | GPIO (BCM) | Physical Pin | Direction |
|-----------|-----------|-------------|-----------|
| PIR Sensor | GPIO 17 | Pin 11 | INPUT |
| LED | GPIO 27 | Pin 13 | OUTPUT |
| Buzzer (passive) | GPIO 22 | Pin 15 | PWM OUTPUT |
| DHT11 Data | GPIO 4 | Pin 7 | INPUT |
| LCD RS | GPIO 26 | Pin 37 | OUTPUT |
| LCD E | GPIO 19 | Pin 35 | OUTPUT |
| LCD D4 | GPIO 13 | Pin 33 | OUTPUT |
| LCD D5 | GPIO 6 | Pin 31 | OUTPUT |
| LCD D6 | GPIO 5 | Pin 29 | OUTPUT |
| LCD D7 | GPIO 11 | Pin 23 | OUTPUT |
| RTC SDA | GPIO 2 | Pin 3 | I2C |
| RTC SCL | GPIO 3 | Pin 5 | I2C |

## New Dependencies

```
gpiozero>=2.0
adafruit-circuitpython-dht
RPLCD
smbus2
```
