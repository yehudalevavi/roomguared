#!/bin/bash
# setup_audio.sh — Install and configure audio system packages
# for Spotify + Bluetooth speaker integration on Raspberry Pi.
#
# Usage: sudo bash config/setup_audio.sh

set -e

echo "=== Room Guard Audio Setup ==="
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
  echo "ERROR: Please run as root (sudo bash config/setup_audio.sh)"
  exit 1
fi

# 1. System packages
echo "[1/5] Installing system packages..."
apt update -qq
apt install -y bluez pulseaudio pulseaudio-module-bluetooth

echo "[2/5] Enabling Bluetooth service..."
systemctl enable bluetooth
systemctl start bluetooth

# 3. PulseAudio Bluetooth modules
echo "[3/5] Configuring PulseAudio Bluetooth modules..."
PA_CONF="/etc/pulse/default.pa"
if [ -f "$PA_CONF" ]; then
  grep -q "module-bluetooth-discover" "$PA_CONF" || \
    echo "load-module module-bluetooth-discover" >> "$PA_CONF"
  grep -q "module-bluetooth-policy" "$PA_CONF" || \
    echo "load-module module-bluetooth-policy" >> "$PA_CONF"
  echo "  PulseAudio config updated"
else
  echo "  WARNING: $PA_CONF not found — PulseAudio may use defaults"
fi

# 4. spotifyd
echo "[4/5] Installing spotifyd..."
if command -v spotifyd &>/dev/null; then
  echo "  spotifyd already installed: $(spotifyd --version 2>/dev/null || echo 'unknown version')"
else
  echo "  Downloading spotifyd binary..."
  ARCH=$(dpkg --print-architecture)
  if [ "$ARCH" = "armhf" ] || [ "$ARCH" = "arm64" ]; then
    wget -q "https://github.com/Spotifyd/spotifyd/releases/latest/download/spotifyd-linux-${ARCH}-default.tar.gz" -O /tmp/spotifyd.tar.gz
    tar xzf /tmp/spotifyd.tar.gz -C /tmp/
    mv /tmp/spotifyd /usr/local/bin/spotifyd
    chmod +x /usr/local/bin/spotifyd
    rm /tmp/spotifyd.tar.gz
    echo "  spotifyd installed to /usr/local/bin/spotifyd"
  else
    echo "  WARNING: Unsupported architecture '$ARCH' — install spotifyd manually"
  fi
fi

# Create spotifyd config if not exists
SPOTIFYD_CONF="/etc/spotifyd.conf"
if [ ! -f "$SPOTIFYD_CONF" ]; then
  cat > "$SPOTIFYD_CONF" << 'CONF'
[global]
device_name = "Room Guard"
backend = "pulseaudio"
bitrate = 320
volume_normalisation = true
normalisation_pregain = -10
cache_path = "/tmp/spotifyd-cache"
CONF
  echo "  Created $SPOTIFYD_CONF"
fi

# Create spotifyd systemd service if not exists
SPOTIFYD_SERVICE="/etc/systemd/system/spotifyd.service"
if [ ! -f "$SPOTIFYD_SERVICE" ]; then
  REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo pi)}"
  cat > "$SPOTIFYD_SERVICE" << EOF
[Unit]
Description=Spotifyd - Spotify Connect daemon
After=network.target sound.target pulseaudio.service bluetooth.service

[Service]
Type=simple
User=${REAL_USER}
ExecStart=/usr/local/bin/spotifyd --no-daemon --config-path /etc/spotifyd.conf
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  echo "  Created spotifyd systemd service"
fi

echo "[5/5] Enabling and starting spotifyd..."
systemctl enable spotifyd
systemctl start spotifyd || echo "  WARNING: spotifyd failed to start — check logs with: journalctl -u spotifyd"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Create a Spotify Developer App at https://developer.spotify.com/dashboard"
echo "  2. Set redirect URI: http://room-guard.local:5000/api/spotify/callback"
echo "  3. Enter credentials in the Room Guard dashboard"
echo "  4. Pair your Bluetooth speaker from the dashboard"
echo ""
echo "For detailed instructions: docs/SPOTIFY_SETUP.md"
