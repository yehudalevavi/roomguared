# 🌡️ Smart Room Dashboard — Implementation Plan

> Evolving the Room Guard into a room monitoring station with temperature, humidity, LCD display, RTC clock, and data logging.

## Approach

Build incrementally — one component at a time. Each phase adds one new hardware piece with its own test script, so you can validate wiring before moving on. The final phase integrates everything into the existing Room Guard.

## Existing Setup (already working)

All components share power via the **breadboard power rails** — one wire from RPi Pin 2 (5V) to the `+` rail, one from RPi Pin 6 (GND) to the `−` rail. Each component taps VCC/GND from these rails.

| Component | GPIO (BCM) | Physical Pin |
|-----------|-----------|-------------|
| 5V Power Rail | — | Pin 2 → breadboard + rail |
| GND Rail | — | Pin 6 → breadboard − rail |
| PIR Sensor OUT | GPIO 17 | Pin 11 |
| LED (+) | GPIO 27 | Pin 13 |
| Buzzer (+) | GPIO 22 | Pin 15 |

---

## Phase 1: DHT11 Temperature & Humidity Sensor

**Status: ⏸️ Code-complete — waiting for hardware**

> The sensor module and unit tests are implemented and committed. When you have the physical DHT11 sensor, complete the remaining steps below.

**Goal:** Read temperature and humidity, print to console.

**New wiring (1 data wire — power from breadboard rails):**

| Wire | From | To |
|------|------|----|
| VCC (red) | DHT11 `+` pin | Breadboard + rail |
| DATA (yellow) | DHT11 `out` pin | RPi Pin 7 (GPIO 4) |
| GND (black) | DHT11 `-` pin | Breadboard − rail |

> The DHT11 module on the Elegoo kit has a built-in pull-up resistor, so no extra resistor needed.

**Software (done ✅):**
- Install `adafruit-circuitpython-dht` library
- `src/dht11_sensor.py` — sensor module with retry logic and value validation
- `src/test_dht11.py` — hardware test that takes 10 readings
- `tests/test_dht11_unit.py` — unit tests (pass without hardware)

**When the sensor arrives — remaining steps:**
1. **Wire** the DHT11 to the breadboard using the table above (power off the Pi first!)
2. **Test** hardware: `source .venv/bin/activate && python3 src/test_dht11.py` — expect ≥8/10 successful reads
3. **Integrate** the sensor into `room_guard.py` — import `DHT11Sensor`, read on each motion event, and include temperature/humidity in the log output
4. **Validate** that the Room Guard still works end-to-end with the sensor added

**Validation:**
- ✅ Temperature shows a reasonable value (15–35°C indoors)
- ✅ Humidity shows a reasonable value (20–80%)
- ✅ No read errors for at least 8 out of 10 readings

---

## Phase 2: Passive Buzzer with Melodies & Sound Cues

**Status: ✅ Complete**

**Goal:** Replace the active buzzer with the passive buzzer to play real melodies and distinct audio cues for different events.

**Why:** The active buzzer can only make one tone (on/off). The passive buzzer can play any frequency, enabling recognizable melodies for the alarm and short sound cues for other system events.

**New wiring (swap 1 component — same pin):**

| Change | From | To |
|--------|------|----|
| Disconnect active buzzer from GPIO 22 | Active buzzer (+) | — |
| Connect passive buzzer to GPIO 22 | Passive buzzer (+) | RPi Pin 15 (GPIO 22) |
| Connect passive buzzer GND | Passive buzzer (−) | Breadboard − rail |

> Same pin (GPIO 22), just swap the buzzer component. The passive buzzer is slightly larger and has **no** white sticker/marking on top (unlike the active buzzer which has one).

**Software (done ✅):**
- `src/buzzer.py` — reusable buzzer module with:
  - `play_tone(frequency, duration)` — play a single tone using PWM
  - `play_melody(notes)` — play a sequence of (frequency, duration) tuples
  - Full chromatic scale constants (octaves 4-5)
  - System melodies: `MELODY_STARTUP`, `MELODY_ARM`, `MELODY_DISARM`, `MELODY_SENSOR_ERROR`
- `src/melody_library.py` — library of **20 famous public-domain melodies** for motion alerts:
  - Twinkle Twinkle Little Star, Ode to Joy, Eine kleine Nachtmusik,
    Für Elise, Happy Birthday, Jingle Bells, Mary Had a Little Lamb,
    London Bridge, Frère Jacques, Beethoven's Fifth, Canon in D,
    Brahms' Lullaby, William Tell Overture, La Cucaracha,
    When the Saints Go Marching In, Row Row Row Your Boat,
    Yankee Doodle, Oh! Susanna, Greensleeves, Old MacDonald
  - `get_random_melody()` — returns a random (name, notes) tuple
- `src/test_buzzer.py` — hardware test that plays system melodies + 3 random samples
- `tests/test_buzzer_unit.py` — 32 unit tests for tone/melody logic + library validation
- Updated `room_guard.py`:
  - Motion detected → random melody from library (name logged)
  - Startup → `MELODY_STARTUP` jingle
  - Shutdown → `MELODY_DISARM` sign-off

**Validation:**
- ✅ Each melody plays distinctly and is recognizable
- ✅ Tones sound at correct pitch (not just clicking)
- ✅ Motion alert plays a random melody each time, logged by name
- ✅ Existing LED behavior is unaffected
- ✅ 32 unit tests pass without hardware

---

## Phase 3: Web-Based Control Panel

**Goal:** Create a lightweight web UI served from the Pi to control the Room Guard from any device on the local network (phone, laptop, etc.) at `http://room-guard:5000`.

**Why:** Right now, controlling the Room Guard requires SSH access and command-line skills. A simple web dashboard lets anyone in the family start/stop the sensor, play melodies, and toggle the LED — all from a browser.

**New wiring:** None — software only.

**Dependencies:** `flask` (added to `requirements.txt`)

**Software:**
- Create `src/web_app.py` — Flask application with a simple responsive HTML UI:
  - **Motion Sensor**: Start / Stop / Status indicator (watching / paused / cooldown)
  - **Buzzer**: Play any of the 20 melodies on demand (dropdown + play button), stop playback
  - **LED**: Toggle on / off
  - **System**: Show uptime, last motion event time, total motion count
  - **Logs**: Show recent motion events with melody names (scrollable, auto-refresh)
- Refactor `room_guard.py` to expose control functions:
  - `arm()` / `disarm()` — enable/disable PIR motion detection
  - `play_melody_by_name(name)` — play a specific melody
  - `set_led(on: bool)` — manual LED control
  - `get_status()` — return current state (armed/disarmed, motion count, last event, etc.)
- Create `src/templates/index.html` — single-page responsive dashboard
  - Mobile-friendly (works on phone browsers)
  - Auto-refreshes status every few seconds via AJAX
  - No external CDN dependencies (works offline on local network)
- Create `tests/test_web_unit.py` — unit tests for Flask routes (mocked hardware)
- Update `config/room_guard.service` to run the Flask app (or run both together)

**Architecture:**
```
Browser (phone/laptop)          Raspberry Pi
┌──────────────┐     HTTP      ┌──────────────────────┐
│  Dashboard   │◄────────────► │  Flask (port 5000)   │
│  index.html  │   local net   │        │              │
└──────────────┘               │  room_guard module   │
                               │   ├── PIR sensor     │
                               │   ├── LED            │
                               │   ├── Buzzer         │
                               │   └── Melody library │
                               └──────────────────────┘
```

**API Endpoints (planned):**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard HTML page |
| GET | `/api/status` | JSON: armed, motion count, last event, LED state |
| POST | `/api/arm` | Enable motion detection |
| POST | `/api/disarm` | Disable motion detection |
| POST | `/api/led/on` | Turn LED on |
| POST | `/api/led/off` | Turn LED off |
| POST | `/api/play/<name>` | Play a specific melody by name |
| GET | `/api/melodies` | List all available melody names |
| GET | `/api/logs` | Recent motion events (JSON) |

**Validation:**
- ✅ Dashboard loads on `http://room-guard:5000` from phone and laptop
- ✅ Start/stop motion detection works from the UI
- ✅ LED toggle responds immediately
- ✅ Melody plays on demand when selected from the list
- ✅ Status auto-refreshes (armed state, motion count, last event)
- ✅ Service runs correctly via systemd
- ✅ Unit tests pass without hardware

**Future extensions (Phase 3+):**
- Add temperature/humidity display when DHT11 sensor is available
- Add LCD control (send custom text to the display)
- Add system controls (reboot Pi, view system info)

---

## Phase 4: LCD1602 Display (4-bit parallel mode)

**Goal:** Display text on the LCD screen.

**New wiring (12 wires + potentiometer):**

The LCD1602 has 16 pins along the top. Wire them as follows:

| LCD Pin | LCD Label | Connect To | Notes |
|---------|-----------|-----------|-------|
| 1 | VSS | Breadboard − rail | Ground |
| 2 | VDD | Breadboard + rail | Power |
| 3 | V0 | Potentiometer wiper | Contrast adjustment |
| 4 | RS | RPi Pin 37 (GPIO 26) | Register Select |
| 5 | RW | Breadboard − rail | Ground = Write mode |
| 6 | E | RPi Pin 35 (GPIO 19) | Enable |
| 7 | D0 | — | Not connected |
| 8 | D1 | — | Not connected |
| 9 | D2 | — | Not connected |
| 10 | D3 | — | Not connected |
| 11 | D4 | RPi Pin 33 (GPIO 13) | Data bit 4 |
| 12 | D5 | RPi Pin 31 (GPIO 6) | Data bit 5 |
| 13 | D6 | RPi Pin 29 (GPIO 5) | Data bit 6 |
| 14 | D7 | RPi Pin 23 (GPIO 11) | Data bit 7 |
| 15 | A | Breadboard + rail via 220Ω | Backlight + |
| 16 | K | Breadboard − rail | Backlight − |

**Potentiometer wiring (for contrast):**

| Potentiometer Pin | Connect To |
|-------------------|-----------|
| Left leg | Breadboard + rail |
| Right leg | Breadboard − rail |
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

## Phase 5: DHT11 + LCD Integration

**Goal:** Show live temperature and humidity on the LCD.

**New wiring:** None — uses Phase 1 + Phase 4 wiring.

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

## Phase 6: DS1307 RTC Module (Real-Time Clock)

**Goal:** Get accurate timestamps even without internet.

**New wiring (2 wires — power from breadboard rails):**

| Wire | From | To |
|------|------|----|
| VCC (red) | DS1307 VCC | Breadboard + rail |
| GND (black) | DS1307 GND | Breadboard − rail |
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

## Phase 7: Smart Room Dashboard (Full Integration)

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

## Phase 8 (Optional/Bonus): Photoresistor Light Level

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
| 5V Power Rail | — | Pin 2 → breadboard + rail | POWER |
| GND Rail | — | Pin 6 → breadboard − rail | GROUND |
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

> All component VCC/GND pins connect to the breadboard power rails, not directly to RPi pins.

## New Dependencies

```
gpiozero>=2.0
adafruit-circuitpython-dht
RPLCD
smbus2
```
