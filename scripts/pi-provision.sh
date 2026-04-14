#!/bin/bash
# Pi Spine — Provisioning Script
# Run on Raspberry Pi 5 after first boot
# Usage: bash pi-provision.sh

set -e

echo "=========================================="
echo "  Pi Spine v0 — Provisioning"
echo "  $(date -Iseconds)"
echo "=========================================="

# Update system
echo "[1/7] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install core tools
echo "[2/7] Installing core dev tools..."
sudo apt install -y \
    python3 python3-pip python3-venv \
    git vim htop screen minicom \
    build-essential cmake \
    usbutils \
    jq

# Install Python packages (system-wide for simplicity in dev)
echo "[3/7] Installing Python packages..."
pip install --break-system-packages \
    pyserial \
    esptool \
    flask

# Install arduino-cli
echo "[4/7] Installing arduino-cli..."
if ! command -v arduino-cli &> /dev/null; then
    curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
    sudo mv bin/arduino-cli /usr/local/bin/
    rm -rf bin
fi

# Set up arduino-cli for ESP32
echo "[5/7] Configuring arduino-cli for ESP32..."
arduino-cli config init || true
arduino-cli config add board_manager.additional_urls \
    https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32

# Install ESP32 libraries used by MiKoBots firmware
echo "[6/7] Installing ESP32 libraries..."
arduino-cli lib install "ESP32Servo"
arduino-cli lib install "TaskScheduler"

# Create project directory structure
echo "[7/7] Setting up project directories..."
mkdir -p ~/pi-spine/{scripts,firmware,config,logs,backups}

# Set up serial port permissions
sudo usermod -a -G dialout $USER

# Create useful aliases
cat >> ~/.bashrc << 'EOF'

# Pi Spine shortcuts
alias spine-logs='tail -f ~/pi-spine/logs/spine-*.log'
alias spine-motion='screen /dev/ttyUSB0 57600'
alias spine-io='screen /dev/ttyUSB1 57600'
alias spine-ports='ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null'
EOF

echo ""
echo "=========================================="
echo "  Provisioning complete!"
echo "=========================================="
echo ""
echo "  IMPORTANT: Log out and back in for serial"
echo "  port permissions to take effect."
echo ""
echo "  Then verify:"
echo "    python3 --version"
echo "    esptool.py version"
echo "    arduino-cli version"
echo "    spine-ports   (after plugging in ESPs)"
echo ""
echo "  Next step: Plug in ESPs, then run:"
echo "    python3 ~/pi-spine/scripts/identify-nodes.py"
echo ""
