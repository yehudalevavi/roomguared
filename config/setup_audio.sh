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

# 4. Spotify Connect daemon (raspotify — packaged librespot for Raspberry Pi)
echo "[4/5] Installing raspotify..."
if command -v librespot &>/dev/null || dpkg -l raspotify &>/dev/null 2>&1; then
  echo "  raspotify already installed"
else
  echo "  Installing raspotify via official script..."
  curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
fi

# Configure device name
RASPOTIFY_CONF="/etc/raspotify/conf"
if [ -f "$RASPOTIFY_CONF" ]; then
  if grep -q '^#LIBRESPOT_NAME=' "$RASPOTIFY_CONF"; then
    sed -i 's|^#LIBRESPOT_NAME=.*|LIBRESPOT_NAME="Room Guard"|' "$RASPOTIFY_CONF"
    echo "  Set device name to 'Room Guard'"
  fi
fi

echo "[5/5] Enabling and starting raspotify..."
systemctl enable raspotify
systemctl restart raspotify || echo "  WARNING: raspotify failed to start — check logs with: journalctl -u raspotify"

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
