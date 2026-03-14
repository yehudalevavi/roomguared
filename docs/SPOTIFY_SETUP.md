# Spotify + Bluetooth Speaker Setup Guide

This guide covers how to set up the Raspberry Pi to stream Spotify music through a JBL Flip 7 (or any A2DP Bluetooth speaker).

## Architecture

```
Spotify Cloud → raspotify/librespot (on Pi) → ALSA/PulseAudio → Bluetooth A2DP → JBL Flip 7
```

- **raspotify**: packaged librespot daemon — handles Spotify Connect audio streaming
- **Room Guard Flask app**: controls playback via Spotify Web API (spotipy)
- **PulseAudio**: routes audio from raspotify to the Bluetooth speaker

## Prerequisites

- Raspberry Pi 4 running Raspberry Pi OS (Bookworm or later)
- JBL Flip 7 (or any Bluetooth A2DP speaker)
- **Spotify Premium account** (required for Spotify Connect)

## Step 1: Install System Packages

Run the automated setup script:

```bash
sudo bash config/setup_audio.sh
```

Or install manually:

```bash
sudo apt update
sudo apt install -y bluez pulseaudio pulseaudio-module-bluetooth
```

## Step 2: Install raspotify (Spotify Connect daemon)

raspotify is a packaged version of librespot specifically for Raspberry Pi.

```bash
curl -sL https://dtcooper.github.io/raspotify/install.sh | sudo sh
```

### Configure raspotify

Edit `/etc/raspotify/conf` and set the device name:

```bash
sudo nano /etc/raspotify/conf
```

Uncomment and set:
```
LIBRESPOT_NAME="Room Guard"
```

Then restart:
```bash
sudo systemctl restart raspotify
```

Verify it's running:
```bash
sudo systemctl status raspotify
```

## Step 3: Configure PulseAudio for Bluetooth

PulseAudio should auto-detect the Bluetooth module. Verify:

```bash
pactl list modules | grep bluetooth
```

If the bluetooth module isn't loaded:

```bash
# Add to /etc/pulse/default.pa:
echo "load-module module-bluetooth-discover" | sudo tee -a /etc/pulse/default.pa
echo "load-module module-bluetooth-policy" | sudo tee -a /etc/pulse/default.pa

# Restart PulseAudio
pulseaudio --kill
pulseaudio --start
```

## Step 4: Create a Spotify Developer App

1. Go to https://developer.spotify.com/dashboard
2. Click **Create App**
3. Set the following:
   - **App name**: Room Guard
   - **App description**: Room Guard Spotify integration
   - **Redirect URI**: `http://room-guard.local:5000/api/spotify/callback`
4. Note your **Client ID** and **Client Secret**

## Step 5: Connect via Room Guard Dashboard

1. Open the Room Guard dashboard: `http://room-guard.local:5000`
2. In the **Spotify** card, enter your Client ID and Client Secret, then click **Save**
3. Click **Connect Spotify** — a new browser tab opens to Spotify login
4. Log in with your Spotify Premium account and authorize the app
5. You'll see "Spotify connected!" — return to the dashboard

## Step 6: Pair the Bluetooth Speaker

1. Turn on your JBL Flip 7 and put it in **pairing mode** (hold the Bluetooth button until it blinks)
2. In the Room Guard dashboard, go to the **Bluetooth Speaker** card
3. Click **Scan Devices** — wait for the scan to complete
4. Find "JBL Flip 7" in the list and click **Connect**
5. The badge should show "● Connected"

After initial pairing, the speaker will auto-reconnect on startup (if powered on and in range).

## Step 7: Play Music!

- **Dashboard**: Click **🎲 Play Random Song** in the Now Playing section
- **IR Remote**: Press the **EQ** button to play a random liked song
- **NFC Card**: Register a card with the "Play random song (Spotify)" action

## Troubleshooting

### No sound from speaker

1. Check Bluetooth connection: `bluetoothctl info` should show "Connected: yes"
2. Check PulseAudio sink: `pactl list sinks short` — look for the BT device
3. Set BT device as default sink: `pactl set-default-sink <sink_name>`
4. Check raspotify is running: `sudo systemctl status raspotify`

### raspotify not showing in Spotify

1. Ensure raspotify is running: `sudo systemctl status raspotify`
2. Check logs: `sudo journalctl -u raspotify -f`
3. Verify PulseAudio is running: `pulseaudio --check && echo "running"`
4. The Pi and your phone/computer must be on the same network

### Bluetooth pairing fails

1. Ensure the speaker is in pairing mode (blinking Bluetooth LED)
2. Try from command line: `bluetoothctl scan on`, then `pair <address>`
3. Check the Pi's Bluetooth adapter: `bluetoothctl show`
4. Reset Bluetooth: `sudo systemctl restart bluetooth`

### Token refresh fails

1. Delete the token file: `rm config/spotify.json`
2. Re-enter credentials and re-authenticate via the dashboard
3. Ensure your redirect URI matches exactly: `http://room-guard.local:5000/api/spotify/callback`

### Audio routing to wrong output

```bash
# List all sinks
pactl list sinks short

# Set the Bluetooth speaker as default
pactl set-default-sink bluez_sink.XX_XX_XX_XX_XX_XX.a2dp_sink

# Verify
pactl info | grep "Default Sink"
```

### Bluetooth connection drops after ~1-2 minutes

This is a known issue with the JBL Flip 7 ↔ Pi 4 A2DP connection. The connection is stable while audio is streaming but drops during idle periods. See [`docs/BLUETOOTH_TROUBLESHOOTING.md`](BLUETOOTH_TROUBLESHOOTING.md) for full analysis, the reliable reconnect sequence, and potential fixes.
