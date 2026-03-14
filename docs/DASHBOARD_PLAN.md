# 🌡️ Smart Room Dashboard — Implementation Plan

> Evolving the Room Guard into a room monitoring station with temperature, humidity, LCD display, IR remote control, NFC card reader, and data logging.

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

**Status: ✅ Complete**

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

**Status: ✅ Complete**

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
| 14 | D7 | RPi Pin 32 (GPIO 12) | Data bit 7 *(reassigned from GPIO 11 — see Phase 9)* |
| 15 | A | Breadboard + rail via 220Ω | Backlight + |
| 16 | K | Breadboard − rail | Backlight − |

**Potentiometer wiring (for contrast):**

| Potentiometer Pin | Connect To |
|-------------------|-----------|
| Left leg | Breadboard + rail |
| Right leg | Breadboard − rail |
| Middle leg (wiper) | LCD Pin 3 (V0) |

> After powering on, slowly turn the potentiometer until you see solid rectangles on the LCD top row — that means contrast is correct.

**Software (done ✅):**
- Install `RPLCD` library (added to `requirements.txt`)
- `src/lcd_display.py` — LCD module with:
  - `LCDDisplay` class with start/stop lifecycle
  - `write(line1, line2)` — write text with automatic truncation and padding
  - `clear()` — clear both lines
  - Change-detection cache to reduce flicker (only rewrites changed lines)
  - `line1`/`line2` read-only properties for current display content
- `src/test_lcd.py` — hardware test that displays "Hello Room Guard!" and cycles through text patterns
- `tests/test_lcd_unit.py` — 27 unit tests (pass without hardware)

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

## Phase 6: IR Remote Control

**Status: ✅ Complete**

> The IR receiver module, unit tests, and hardware tests are implemented, deployed, and tested on the Pi. The remote controls arm/disarm, melody navigation, and play/stop — working alongside the web dashboard.

**Goal:** Use an IR receiver and remote control to physically control the Room Guard — arm/disarm the alarm, navigate and play melodies, and more.

**Why:** The web dashboard is great for phones and laptops, but sometimes you just want to grab a remote and press a button. An IR remote gives instant physical control without needing a network connection or a browser — perfect for a bedside alarm or a quick "shut up!" when a melody is playing.

**New wiring (1 data wire — power from breadboard rails):**

| Wire | From | To |
|------|------|----|
| VCC (red) | IR receiver VCC | RPi Pin 1 (3.3V) |
| Signal (yellow) | IR receiver Signal | RPi Pin 12 (GPIO 18) |
| GND (black) | IR receiver GND | Breadboard − rail |

> The IR receiver module (e.g., VS1838B from the Elegoo kit) has 3 pins: Signal, VCC, and GND. Orient the rounded dome side toward the remote. Some modules have the pins labeled; if not, check the datasheet — pin order varies by module.
>
> ⚠️ **Power the IR receiver from 3.3V, not 5V.** The signal pin connects directly to a GPIO pin, and RPi GPIOs are 3.3V only. Powering from 5V could send 5V into the GPIO and damage the Pi. The VS1838B works fine at 3.3V (rated 2.7–5.5V).

**System setup:**
- Enable the `gpio-ir-recv` kernel overlay by adding to `/boot/config.txt`:
  ```
  dtoverlay=gpio-ir,gpio_pin=18
  ```
- Reboot the Pi for the overlay to take effect
- Install `ir-keytable` for scanning and configuring key mappings:
  ```bash
  sudo apt install -y ir-keytable
  ```
- Verify the IR device is detected:
  ```bash
  ir-keytable
  ```
  Should show an `rc` device using the `gpio_ir_recv` driver.

**Software (done ✅):**
- `src/ir_remote.py` — IR remote handler module:
  - `IRRemote` class that listens for IR scancode events via `evdev`
  - Configurable scancode-to-action mapping (easy to remap for different remotes)
  - 1000ms debounce to suppress NEC protocol repeat codes
  - Runs in a background daemon thread, dispatches actions to the `RoomGuard` instance
- `src/test_ir.py` — hardware test that prints received scancodes/keycodes (useful for mapping a new remote)
- `tests/test_ir_unit.py` — 21 unit tests for config, dispatch, lifecycle, and debounce logic
- Added `evdev>=1.7` to `requirements.txt`
- Added `RoomGuard` methods: `next_melody()`, `prev_melody()`, `play_current_melody()`, `stop_melody()`, `toggle_arm()`
- Added web API endpoints: `POST /api/melody/next`, `POST /api/melody/prev`, `POST /api/melody/play`, `POST /api/melody/stop`, `POST /api/toggle-arm`
- Added buzzer cancel mechanism (`threading.Event`) for stopping melodies mid-playback
- IR remote auto-starts with the web app and room guard CLI

**Pi configuration (done ✅):**
- `/boot/firmware/config.txt`: `dtoverlay=gpio-ir,gpio_pin=18`
- `/etc/udev/rules.d/99-ir-nec.rules`: Persists NEC protocol across reboots
- NEC protocol must be enabled: `sudo ir-keytable -p nec -s rc0`

**Button mapping (default — configurable):**

| Remote Button | Action | Sound Cue |
|---------------|--------|-----------|
| ⏮ Prev (\ |<<) | Select previous melody in library | Short low beep |
| ⏯ Play/Pause (>\ |\ |) | Play selected melody / stop if playing | — |
| ⏭ Next (>>\ |) | Select next melody in library | Short high beep |
| 🔴 Red button | Toggle arm / disarm | `MELODY_ARM` or `MELODY_DISARM` jingle |

> The "current melody" selection wraps around: pressing Next on the last melody goes back to the first, and Prev on the first goes to the last. The LCD shows the currently selected melody name when navigating with Prev/Next.

**Suggested future button mappings:**

| Remote Button | Potential Action |
|---------------|-----------------|
| 0 | Play a random melody |
| 1–9 | Quick-play melody by number |
| CH−/CH/CH+ | Cycle LCD display pages |
| EQ | Toggle LED on/off |
| +/− | Adjust motion cooldown time |
| Power | Graceful Pi shutdown (long-press for safety) |

**Integration with Room Guard (done ✅):**
- `RoomGuard` gains new methods:
  - `next_melody()` — advance the internal melody index, return the name
  - `prev_melody()` — go back one melody, return the name
  - `play_current_melody()` — play the currently selected melody
  - `stop_melody()` — interrupt a playing melody (sets a cancel flag checked in the play loop)
  - `toggle_arm()` — arm if disarmed, disarm if armed, with `MELODY_ARM` / `MELODY_DISARM` sound cue
- Arm/disarm via remote plays the existing system melodies (`MELODY_ARM` and `MELODY_DISARM` from `buzzer.py`) that were defined but previously unused
- Web API gains matching endpoints: `POST /api/play/next`, `POST /api/play/prev`, `POST /api/toggle-arm`

**Validation:**
- ✅ `test_ir.py` prints button codes when remote buttons are pressed
- ✅ Prev/Next cycle through all 20 melodies (wraps around)
- ✅ Play/Pause starts and stops melody playback
- ✅ Red button arms/disarms with audible jingle confirmation
- ✅ LCD shows selected melody name during navigation
- ✅ IR remote works simultaneously with the web dashboard (no conflicts)
- ✅ Unit tests pass without hardware

---

## Phase 7: Smart Room Dashboard (Full Integration)

**Goal:** Merge all components into an upgraded `room_guard.py`.

**New wiring:** None — all wired in previous phases.

**Software — new features:**
- LCD screen cycles between pages (every 5 seconds):
  - Page 1: `Temp: 23.0C` / `Humidity: 45%`
  - Page 2: `Motion: 7 today` / `Last: 14:23:05`
  - Page 3: `Room Guard ON` / `<current date/time>`
- Motion events are timestamped using the system clock (NTP-synced when online)
- IR remote provides physical controls alongside the web dashboard
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

## Phase 9: NFC Card Reader (MFRC522)

**Status: ✅ Complete**

**Goal:** Use the MFRC522 RFID/NFC reader to let household members tap NFC cards or key fobs to control the Room Guard — arm/disarm, toggle the LED, play melodies, and more.

**Why:** The IR remote is great for nearby control, and the web dashboard works from any device — but NFC adds a different interaction model. Each family member gets their own card with a personalized action. Tap to arm when leaving, tap to disarm when arriving — no phone needed, no buttons to find in the dark.

**New wiring (7 wires — all direct to RPi, no breadboard):**

The MFRC522 module uses SPI (Serial Peripheral Interface). It connects directly to the RPi's dedicated SPI0 pins and power — no breadboard needed.

| Wire | From | To | Notes |
|------|------|----|-------|
| SDA | MFRC522 SDA | RPi Pin 24 (GPIO 8) | SPI chip select (CE0) |
| SCK | MFRC522 SCK | RPi Pin 23 (GPIO 11) | SPI clock |
| MOSI | MFRC522 MOSI | RPi Pin 19 (GPIO 10) | SPI data out |
| MISO | MFRC522 MISO | RPi Pin 21 (GPIO 9) | SPI data in |
| RST | MFRC522 RST | RPi Pin 22 (GPIO 25) | Reset |
| 3.3V | MFRC522 VCC | RPi Pin 17 (3.3V) | ⚠️ Must use 3.3V, not 5V |
| GND | MFRC522 GND | RPi Pin 20 (GND) | Ground |
| IRQ | MFRC522 IRQ | — | Not connected (not needed) |

> ⚠️ **Power the MFRC522 from 3.3V, not 5V.** The module operates at 3.3V logic. The SPI pins connect directly to RPi GPIOs which are 3.3V-only — using 5V risks damaging the Pi.
>
> ⚠️ **GPIO 11 conflict resolved:** GPIO 11 (Pin 23) was previously assigned to LCD D7 in Phase 4. Since the LCD hasn't been wired yet, LCD D7 has been **reassigned to GPIO 12 (Pin 32)**. The Phase 4 wiring table has been updated. During implementation, `lcd_display.py` will also be updated (`LCD_D7 = 12`).

**System setup:**
- Enable SPI interface on the Pi:
  ```bash
  sudo raspi-config nonint do_spi 0
  ```
  Or via `raspi-config` → Interface Options → SPI → Enable
- Reboot for the change to take effect
- Verify SPI is enabled:
  ```bash
  ls /dev/spidev*
  ```
  Should show `/dev/spidev0.0` and `/dev/spidev0.1`

**Software (done ✅):**
- Install `mfrc522` and `spidev` libraries (add to `requirements.txt`)
- Update `src/lcd_display.py` — change `LCD_D7` from GPIO 11 to GPIO 12
- Create `src/nfc_reader.py` — NFC reader module:
  - `NFCReader` class that polls for cards in a background daemon thread
  - Configurable UID-to-action mapping (loaded from `config/nfc_cards.json`)
  - Card tap detection with ~2 second debounce to prevent repeat triggers
  - Confirmation beep on successful card read (short high tone)
  - Error beep for unregistered cards (short low tone)
  - `register_card(uid, action, label)` — add a new card mapping
  - `remove_card(uid)` — remove a card mapping
  - `get_registered_cards()` — list all registered cards
- Create `config/nfc_cards.json` — card UID → action mapping:
  ```json
  {
    "cards": [
      {
        "uid": "0x1A2B3C4D",
        "action": "toggle_arm",
        "label": "Dad's key fob"
      },
      {
        "uid": "0x5E6F7A8B",
        "action": "toggle_led",
        "label": "White card"
      }
    ]
  }
  ```
- Create `src/test_nfc.py` — hardware test:
  - Scans for cards and prints UIDs (useful for registering new cards)
  - Tests read reliability (10 consecutive reads)
- Create `tests/test_nfc_unit.py` — unit tests (pass without hardware):
  - Config loading/saving
  - UID-to-action dispatch
  - Debounce logic
  - Registration/removal
- Add web API endpoints:
  - `GET /api/nfc/cards` — list registered cards and their actions
  - `POST /api/nfc/register` — enter scan mode, tap card to register with an action
  - `DELETE /api/nfc/cards/<uid>` — remove a card mapping
  - `GET /api/nfc/last-scan` — last scanned card UID and timestamp
- Add NFC card management section to the web dashboard UI

**Supported actions (mapped per card):**

| Action | Description | Sound Cue |
|--------|-------------|-----------|
| `toggle_arm` | Arm if disarmed, disarm if armed | `MELODY_ARM` / `MELODY_DISARM` jingle |
| `toggle_led` | Toggle LED on/off | Short confirmation beep |
| `play_melody:<name>` | Play a specific melody by name | The melody itself |
| `play_random` | Play a random melody from the library | The melody itself |
| `stop_melody` | Stop any currently playing melody | Short low beep |

> New actions can be added easily — the mapping is just a string dispatched to existing `RoomGuard` methods.

**Integration with Room Guard:**
- `RoomGuard` reuses existing methods: `toggle_arm()`, `set_led()`, `play_melody_by_name()`, `stop_melody()` — same ones used by IR remote and web dashboard
- NFC reader auto-starts alongside the web app and IR remote
- Card tap events are logged (timestamp, UID, label, action triggered)
- LCD shows card label briefly when tapped (e.g., `"Dad's fob"` / `"Armed!"`)

**Validation:**
- ✅ `test_nfc.py` detects and prints card UIDs when tapped on the reader
- ✅ Registered card triggers the correct action with confirmation beep
- ✅ Unregistered card plays error beep, does not trigger any action
- ✅ Debounce prevents rapid re-triggers when card is held near reader
- ✅ Web dashboard shows registered cards and allows management
- ✅ NFC works simultaneously with IR remote and web dashboard (no conflicts)
- ✅ Unit tests pass without hardware

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
| IR Receiver | GPIO 18 | Pin 12 | INPUT |
| LCD RS | GPIO 26 | Pin 37 | OUTPUT |
| LCD E | GPIO 19 | Pin 35 | OUTPUT |
| LCD D4 | GPIO 13 | Pin 33 | OUTPUT |
| LCD D5 | GPIO 6 | Pin 31 | OUTPUT |
| LCD D6 | GPIO 5 | Pin 29 | OUTPUT |
| LCD D7 | GPIO 12 | Pin 32 | OUTPUT |
| NFC SDA (CE0) | GPIO 8 | Pin 24 | SPI |
| NFC SCK | GPIO 11 | Pin 23 | SPI |
| NFC MOSI | GPIO 10 | Pin 19 | SPI |
| NFC MISO | GPIO 9 | Pin 21 | SPI |
| NFC RST | GPIO 25 | Pin 22 | OUTPUT |

> All component VCC/GND pins connect to the breadboard power rails, not directly to RPi pins — **except** the MFRC522 NFC reader, which connects directly to RPi Pin 17 (3.3V) and Pin 20 (GND).

## Auto-Update on Service Start

**Status: ✅ Complete**

**Goal:** Ensure the Raspberry Pi always runs the latest firmware by pulling code updates automatically before the application starts.

**Why:** Without this, deploying new features or fixes requires SSH access to the Pi and manually running `git pull`. With auto-update, you just push to the `master` branch and the Pi picks up the changes on its next reboot or service restart — no manual intervention needed.

**New wiring:** None — software only.

**How it works:**

The systemd service (`config/room_guard.service`) uses `ExecStartPre` directives to run two commands before launching the app:

1. `git pull origin master` — fetches and applies the latest code from GitHub
2. `pip install -r requirements.txt` — installs any new or updated dependencies

Both commands use the `-` prefix, which tells systemd to **continue even if they fail** (e.g., no network on boot). This means:
- ✅ If the Pi has internet → it updates to the latest code, then starts
- ✅ If the Pi has no internet → it skips the update and starts with the existing code

The service also waits for `network-online.target` so the network has the best chance of being ready before the pull.

**To deploy new code to the Pi:**
1. Push your changes to `master` on GitHub
2. Either reboot the Pi or run `sudo systemctl restart room_guard`
3. The service pulls the latest code and restarts the app automatically

**Validation:**
- ✅ Service starts normally when network is available (pulls latest code)
- ✅ Service starts normally when network is unavailable (skips pull gracefully)
- ✅ New dependencies in `requirements.txt` are installed automatically
- ✅ Existing Room Guard functionality is unaffected

---

## New Dependencies

```
gpiozero>=2.0
adafruit-circuitpython-dht
RPLCD
evdev
mfrc522
spidev
spotipy>=2.23
```

---

## Phase 10: Spotify + Bluetooth Speaker Integration

**Status: ⚠️ Functional — Bluetooth stability issue open**

> **Known Issue:** The A2DP Bluetooth connection to the JBL Flip 7 drops after ~1-2 minutes of idle time. While connected, audio streaming works perfectly (both test tones and Spotify). Reconnecting requires a full BT+PulseAudio restart sequence — simple `bluetoothctl connect` fails with `br-connection-profile-unavailable`. The software watchdog reconnect loop (15s interval) was found to destabilize the connection further. See [`docs/BLUETOOTH_TROUBLESHOOTING.md`](BLUETOOTH_TROUBLESHOOTING.md) for full analysis, workarounds, and potential fixes to investigate.

**Goal:** Stream Spotify music through a JBL Flip 7 Bluetooth speaker, controlled via IR remote, NFC card, or web dashboard.

### Architecture

```
Spotify Cloud → spotifyd (daemon) → PulseAudio → Bluetooth A2DP → JBL Flip 7
```

- **spotifyd** runs as a separate systemd service making the Pi a Spotify Connect device
- **Room Guard** controls playback via Spotify Web API (spotipy library)
- **BlueZ/bluetoothctl** manages Bluetooth speaker pairing and A2DP connection

### New Files

| File | Purpose |
|------|---------|
| `src/bluetooth_speaker.py` | BlueZ wrapper — scan, pair, connect, disconnect, auto-reconnect |
| `src/spotify_player.py` | Spotify Web API — OAuth2, liked songs, transport controls |
| `config/setup_audio.sh` | System package installer (PulseAudio, BlueZ, spotifyd) |
| `docs/SPOTIFY_SETUP.md` | Full setup guide with troubleshooting |
| `tests/test_bluetooth_unit.py` | 30 unit tests for Bluetooth module |
| `tests/test_spotify_unit.py` | 49 unit tests for Spotify module |
| `tests/test_media_integration.py` | 28 integration tests for RoomGuard media layer |

### Modified Files

| File | Changes |
|------|---------|
| `src/room_guard.py` | Added BluetoothSpeaker + SpotifyPlayer instances, media methods, Now Playing LCD page |
| `src/web_app.py` | 17 new API endpoints (BT + Spotify + OAuth) |
| `src/ir_remote.py` | 6 new transport key mappings (random play, pause, next, prev, vol up/down) |
| `src/nfc_reader.py` | 5 new card actions (play_random_song, spotify_pause/next/prev, play_track) |
| `src/templates/index.html` | 3 new dashboard panels (BT pairing, Spotify auth, Now Playing controls) |
| `requirements.txt` | Added `spotipy>=2.23` |

### API Endpoints

**Bluetooth:**
- `GET /api/bluetooth/status` — connection status
- `POST /api/bluetooth/scan` — discover nearby devices
- `POST /api/bluetooth/pair` — pair + connect to device
- `POST /api/bluetooth/connect` — connect to paired device
- `POST /api/bluetooth/disconnect` — disconnect speaker
- `DELETE /api/bluetooth/device/<address>` — forget device

**Spotify:**
- `GET /api/spotify/status` — auth + playback status
- `POST /api/spotify/credentials` — save client_id + client_secret
- `GET /api/spotify/auth` — get OAuth2 URL
- `GET /api/spotify/callback` — OAuth2 callback handler
- `POST /api/spotify/play-random` — play random liked song
- `POST /api/spotify/play` — play specific track URI
- `POST /api/spotify/pause` — pause playback
- `POST /api/spotify/resume` — resume playback
- `POST /api/spotify/next` — skip next
- `POST /api/spotify/prev` — skip previous
- `POST /api/spotify/volume` — set volume (0-100)
- `GET /api/spotify/devices` — list Spotify Connect devices
- `POST /api/spotify/transfer` — transfer playback to device

### IR Remote Mapping (Elegoo NEC Remote)

| Button | Scancode | Action |
|--------|----------|--------|
| EQ | `0x07` | Play random liked song |
| + | `0x09` | Pause/resume Spotify |
| >> | `0x15` | Next Spotify track |
| << | `0x16` | Previous Spotify track |
| VOL+ | `0x19` | Volume up 10% |
| VOL- | `0x0D` | Volume down 10% |

### NFC Card Actions

| Action | Description |
|--------|-------------|
| `play_random_song` | Play a random song from Spotify liked songs |
| `spotify_pause` | Toggle pause/resume |
| `spotify_next` | Skip to next track |
| `spotify_prev` | Skip to previous track |
| `play_track:<uri>` | Play a specific Spotify track URI |

### Setup Instructions

See `docs/SPOTIFY_SETUP.md` for full setup guide including:
- System package installation
- spotifyd configuration
- Spotify Developer App creation
- OAuth2 authentication flow
- Bluetooth speaker pairing
- Troubleshooting
