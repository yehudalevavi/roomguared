# Spotify + Bluetooth Speaker Setup Guide

This guide covers how to set up the Raspberry Pi to stream Spotify music through a JBL Flip 7 (or any A2DP Bluetooth speaker).

## Architecture

```
Spotify Cloud → spotifyd (on Pi) → PulseAudio → Bluetooth A2DP → JBL Flip 7
```

- **spotifyd**: lightweight Spotify Connect daemon — handles audio streaming
- **Room Guard Flask app**: controls playback via Spotify Web API (spotipy)
- **PulseAudio**: routes audio from spotifyd to the Bluetooth speaker

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

## Step 2: Install spotifyd

### Option A: From apt (if available)

```bash
sudo apt install -y spotifyd
```

### Option B: Download binary

```bash
# Download the latest armhf release
wget https://github.com/Spotifyd/spotifyd/releases/latest/download/spotifyd-linux-armhf-default.tar.gz
tar xzf spotifyd-linux-armhf-default.tar.gz
sudo mv spotifyd /usr/local/bin/
sudo chmod +x /usr/local/bin/spotifyd
```

### Configure spotifyd

Create `/etc/spotifyd.conf`:

```ini
[global]
# The name that shows up in Spotify Connect device list
device_name = "Room Guard"

# Audio backend
backend = "pulseaudio"

# Audio quality (96, 160, or 320 kbps)
bitrate = 320

# Reduce volume normalization for better dynamic range
volume_normalisation = true
normalisation_pregain = -10

# Cache for faster startup
cache_path = "/tmp/spotifyd-cache"

# No password needed — we authenticate via OAuth in Room Guard dashboard
```

### Enable spotifyd as a service

```bash
# If installed via apt:
sudo systemctl enable spotifyd
sudo systemctl start spotifyd

# If using manual binary, create a systemd unit:
sudo tee /etc/systemd/system/spotifyd.service << 'EOF'
[Unit]
Description=Spotifyd - Spotify Connect daemon
After=network.target sound.target pulseaudio.service bluetooth.service

[Service]
Type=simple
User=yehudalevavi
ExecStart=/usr/local/bin/spotifyd --no-daemon --config-path /etc/spotifyd.conf
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable spotifyd
sudo systemctl start spotifyd
```

Verify spotifyd is running:

```bash
sudo systemctl status spotifyd
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
4. Check spotifyd is running: `sudo systemctl status spotifyd`

### spotifyd not showing in Spotify

1. Ensure spotifyd is running: `sudo systemctl status spotifyd`
2. Check spotifyd logs: `sudo journalctl -u spotifyd -f`
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
