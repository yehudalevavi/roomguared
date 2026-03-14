# Bluetooth A2DP Connection — Troubleshooting & Known Issues

> Findings from extensive debugging of the JBL Flip 7 ↔ Raspberry Pi 4 Bluetooth connection (March 2026).

## Current Status

**Bluetooth pairing and audio streaming work**, but the A2DP connection is **unstable** — it drops after roughly 1-2 minutes of idle time. While connected, audio plays successfully through the JBL speaker (both test tones and Spotify via raspotify).

## What Works

| Feature | Status | Notes |
|---------|--------|-------|
| BT pairing (initial) | ✅ | `bluetoothctl pair` while scan is active |
| BT trust | ✅ | Persists across reboots |
| BT connect (manual) | ✅ | `bluetoothctl connect` after BT+PA restart |
| A2DP sink creation | ✅ | PulseAudio creates `bluez_sink.50_1B_6A_FB_7A_85.a2dp_sink` |
| Test sound via BT | ✅ | `play -qn -t pulseaudio synth ...` works through JBL |
| Spotify playback via BT | ✅ | raspotify → PulseAudio → BT → JBL works |
| Spotify credential caching | ✅ | "Room Guard" auto-registers in Spotify devices API on restart |
| Spotify device targeting | ✅ | `_ensure_pi_device()` finds and transfers to "Room Guard" |

## Known Issue: A2DP Connection Drops After ~1-2 Minutes

### Symptoms

- `bluetoothctl info` shows `Connected: yes` but PulseAudio BT sink disappears
- Or `bluetoothctl info` shows `Connected: no` entirely
- Reconnect attempt gets `br-connection-profile-unavailable` error
- Requires full BT+PA restart sequence to reconnect (simple `bluetoothctl connect` fails)

### Observations

1. **The connection is stable while audio is actively streaming.** The drop happens during idle periods.
2. **The JBL Flip 7 has aggressive power management** — it auto-sleeps after a period of no audio, which may trigger the disconnect.
3. **The `br-connection-profile-unavailable` error** specifically means the A2DP audio profile can't be established. This happens when:
   - PulseAudio's bluetooth module has stale state from the dropped connection
   - The BlueZ stack has a stale connection entry
   - Both need to be restarted to clear the state
4. **The watchdog reconnect loop (every 15s) was making things worse** — rapid reconnect attempts destabilized the connection further. The watchdog may need to be disabled or given a much longer interval with exponential backoff.
5. **`bluetoothctl info` showing `Connected: yes` is misleading** — the L2CAP control channel can remain "connected" even after the A2DP audio transport has been torn down. The true test is whether `pactl list sinks short` shows the BT sink.

### Reliable Reconnect Sequence

When the connection drops, this sequence reliably restores it:

```bash
# 1. Restart both bluetooth and PulseAudio to clear stale state
sudo systemctl restart bluetooth
sleep 2
systemctl --user restart pulseaudio
sleep 2

# 2. Power on and connect
bluetoothctl power on
sleep 1
bluetoothctl connect 50:1B:6A:FB:7A:85
sleep 5

# 3. Verify A2DP sink appeared
pactl list sinks short | grep bluez

# 4. Set as default sink
pactl set-default-sink bluez_sink.50_1B_6A_FB_7A_85.a2dp_sink

# 5. Test
play -qn -t pulseaudio synth 0.3 pluck 659.3 : synth 0.4 pluck 880 gain -30
```

**Important:** A simple `bluetoothctl connect` (without restarting BT+PA) almost always fails with `br-connection-profile-unavailable` after a drop.

### What Does NOT Work

| Approach | Result |
|----------|--------|
| `bluetoothctl connect` alone (after drop) | `br-connection-profile-unavailable` |
| Watchdog reconnecting every 15s | Destabilizes the connection, causes more drops |
| Trusting the device (for auto-reconnect) | BlueZ `trust` flag alone doesn't reliably auto-reconnect A2DP sinks |
| Relying on `bluetoothctl info` `Connected: yes` | Does not guarantee A2DP audio is actually active |

## Pairing Notes (JBL Flip 7 Specific)

### Initial Pairing Procedure

```bash
bluetoothctl
# IMPORTANT: Do NOT stop scan before pairing — scan off deletes discovered unpaired devices
scan on
# Wait for JBL to appear (must be in pairing mode — hold BT button until rapid blinking)
pair 50:1B:6A:FB:7A:85
trust 50:1B:6A:FB:7A:85
connect 50:1B:6A:FB:7A:85
```

### Re-pairing After Forget

If the device was removed (`bluetoothctl remove <addr>`), you must:
1. Put JBL in pairing mode (hold BT button ~3s until LED blinks rapidly)
2. Start scan FIRST, then pair while scan is still running
3. The JBL may go to sleep during the process — press the power button to wake it

### Device Details

- **Address:** `50:1B:6A:FB:7A:85`
- **Name:** `רותם של JBL Flip 7` (Hebrew — "Rotem's JBL Flip 7")
- **PulseAudio sink name:** `bluez_sink.50_1B_6A_FB_7A_85.a2dp_sink`

## Raspotify (librespot) + PulseAudio Configuration

### Systemd Override Required

Raspotify's default systemd sandboxing blocks PulseAudio access. A drop-in override is required at `/etc/systemd/system/raspotify.service.d/pulseaudio.conf`:

```ini
[Service]
PrivateUsers=false
ProtectHome=false
PrivateTmp=false
ProtectSystem=full
User=yehudalevavi
Environment=PULSE_SERVER=unix:/run/user/1000/pulse/native
Environment=XDG_RUNTIME_DIR=/run/user/1000
```

**Why each setting:**
- `PrivateUsers=false` — allows access to user's PulseAudio session
- `ProtectHome=false` — allows reading config from home directory
- `PrivateTmp=false` — librespot needs `/tmp` for download buffering
- `ProtectSystem=full` (not `strict`) — `strict` causes `ReadOnlyFilesystem` errors
- `User=yehudalevavi` — run as the user who owns the PulseAudio session
- `PULSE_SERVER` — explicit path to PulseAudio socket
- `XDG_RUNTIME_DIR` — required for PulseAudio client to find the session

### Credential Caching

Raspotify config (`/etc/raspotify/conf`) must have credential caching **enabled** (the disable flag commented out):

```
#LIBRESPOT_DISABLE_CREDENTIAL_CACHE=
LIBRESPOT_CACHE=/var/cache/raspotify
LIBRESPOT_SYSTEM_CACHE=/var/cache/raspotify
```

**Why:** Without credential caching, librespot only works via zeroconf discovery. In zeroconf mode, it does NOT appear in the Spotify Web API `devices()` endpoint until a Spotify client (phone/desktop app) manually connects to it via the device picker. With credential caching:
- First connection must be done manually from the Spotify phone app (one-time)
- Credentials are saved to `/var/cache/raspotify/credentials.json`
- On subsequent restarts, librespot auto-authenticates and appears in the API immediately

### librespot OAuth Limitation

librespot's built-in OAuth client ID (`65b708073fc0480ea92a077233ca87bd`) is **revoked/invalid** — standalone OAuth login through librespot does not work. The only way to establish initial credentials is via zeroconf (phone app device picker).

## Spotify Playback Flow

```
User Action (Web UI / IR / NFC)
    ↓
RoomGuard.play_random_song()
    ↓
SpotifyPlayer._ensure_pi_device()
    ├── Find "Room Guard" in Spotify devices API
    ├── If not found → restart raspotify → wait 5s → retry
    └── Transfer playback to "Room Guard" device
    ↓
SpotifyPlayer.play_random_liked_song()
    ├── Fetch total liked songs count
    ├── Pick random offset → fetch that song
    └── start_playback(device_id=pi_device_id, uris=[track_uri])
    ↓
Spotify Cloud sends audio stream to raspotify/librespot
    ↓
raspotify → PulseAudio default sink → BT A2DP → JBL Flip 7
```

## Potential Fixes to Investigate

### 1. Keep-alive audio stream
Play silent/inaudible audio periodically to prevent the JBL from going to sleep and dropping the A2DP connection. For example, a very low-volume tone every 30s.

### 2. PulseAudio module-loopback
Use PulseAudio's loopback module to keep the BT sink active:
```bash
pactl load-module module-loopback source=auto_null.monitor sink=bluez_sink.50_1B_6A_FB_7A_85.a2dp_sink
```

### 3. Smarter reconnect with full restart
Instead of just `bluetoothctl connect`, the watchdog should do the full restart sequence (restart bluetooth + pulseaudio, then connect). Add exponential backoff (30s → 60s → 120s) to avoid destabilizing the connection.

### 4. BlueZ ControllerMode
Set `ControllerMode = bredr` in `/etc/bluetooth/main.conf` to disable BLE and focus on classic Bluetooth (A2DP uses BR/EDR).

### 5. Disable PulseAudio suspend-on-idle
PulseAudio suspends idle sinks, which may confuse the BT transport:
```bash
# In /etc/pulse/default.pa, comment out:
# load-module module-suspend-on-idle
```

### 6. bluetoothd --noplugin=avrcp
Some JBL speakers have buggy AVRCP (remote control profile) implementations that interfere with A2DP stability.

### 7. JBL firmware update
Check if there's a JBL Flip 7 firmware update via the JBL Portable app that improves Bluetooth stability.

## Test Commands Reference

```bash
# Check BT connection (true state — check for A2DP sink, not just bluetoothctl)
pactl list sinks short | grep bluez

# Quick test sound
play -qn -t pulseaudio synth 0.3 pluck 659.3 : synth 0.4 pluck 880 gain -30

# Check raspotify
sudo systemctl status raspotify
sudo journalctl -u raspotify -f

# Check Spotify devices via Python
cd ~/rpiProject && source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'src')
from spotify_player import SpotifyPlayer
sp = SpotifyPlayer(); sp.start()
print(sp.get_devices())
"

# Full reconnect script
sudo systemctl restart bluetooth && sleep 2 && systemctl --user restart pulseaudio && sleep 2 && bluetoothctl power on && sleep 1 && bluetoothctl connect 50:1B:6A:FB:7A:85 && sleep 5 && pactl set-default-sink bluez_sink.50_1B_6A_FB_7A_85.a2dp_sink
```

## Pi System Configuration Files

| File | Purpose |
|------|---------|
| `/etc/raspotify/conf` | raspotify/librespot config (device name, backend, caching) |
| `/etc/systemd/system/raspotify.service.d/pulseaudio.conf` | PulseAudio access override |
| `/etc/sudoers.d/raspotify-restart` | Passwordless sudo for `systemctl restart raspotify` |
| `/var/cache/raspotify/credentials.json` | Cached Spotify credentials (auto-created) |
| `/etc/bluetooth/main.conf` | BlueZ configuration |
| `config/bluetooth.json` | Room Guard's saved BT device address/name |
