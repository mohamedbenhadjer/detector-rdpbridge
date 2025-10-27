#!/usr/bin/env bash
# Installation script for Playwright Watchdog
# Supports Linux and macOS

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WATCHDOG_DIR="${PW_WATCHDOG_DIR:-$HOME/.pw_watchdog}"

echo "========================================="
echo "Playwright Watchdog Installer"
echo "========================================="
echo ""

# Detect OS
OS="$(uname -s)"
echo "Detected OS: $OS"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3.7 or later."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "Python version: $PYTHON_VERSION"

# Check if pip is available
if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
    echo "Error: pip not found. Please install pip."
    exit 1
fi

echo ""
echo "Installing Python dependencies..."
python3 -m pip install -r "$SCRIPT_DIR/requirements.txt" --user

# Create watchdog directories
echo ""
echo "Creating watchdog directories in $WATCHDOG_DIR..."
mkdir -p "$WATCHDOG_DIR"/{logs,cdp,reports,tmp}
echo "Created: $WATCHDOG_DIR/logs"
echo "Created: $WATCHDOG_DIR/cdp"
echo "Created: $WATCHDOG_DIR/reports"
echo "Created: $WATCHDOG_DIR/tmp"

# Make scripts executable
echo ""
echo "Making scripts executable..."
chmod +x "$SCRIPT_DIR/playwright_watchdog.py"
chmod +x "$SCRIPT_DIR/bin/pw-run.sh"
chmod +x "$SCRIPT_DIR/bin/pw-run-pytest.sh"

# OS-specific setup
if [[ "$OS" == "Linux" ]]; then
    echo ""
    echo "Linux detected. Would you like to install the systemd user service? (y/n)"
    read -r INSTALL_SERVICE
    
    if [[ "$INSTALL_SERVICE" =~ ^[Yy]$ ]]; then
        SYSTEMD_DIR="$HOME/.config/systemd/user"
        mkdir -p "$SYSTEMD_DIR"
        
        # Update service file with correct paths
        sed "s|%h/detector-rdpbridge|$SCRIPT_DIR|g" \
            "$SCRIPT_DIR/systemd/user/pw-watchdog.service" \
            > "$SYSTEMD_DIR/pw-watchdog.service"
        
        echo "Service file installed to $SYSTEMD_DIR/pw-watchdog.service"
        echo ""
        echo "To enable and start the service, run:"
        echo "  systemctl --user enable --now pw-watchdog"
        echo ""
        echo "To check status:"
        echo "  systemctl --user status pw-watchdog"
        echo ""
        echo "To view logs:"
        echo "  journalctl --user -u pw-watchdog -f"
    fi
elif [[ "$OS" == "Darwin" ]]; then
    echo ""
    echo "macOS detected. Service installation not yet automated for macOS."
    echo "You can run the watchdog manually: ./playwright_watchdog.py"
fi

# Create .env if it doesn't exist
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo ""
    echo "Creating default .env file..."
    cat > "$SCRIPT_DIR/.env" << EOF
# Playwright Watchdog Configuration
PW_WATCHDOG_DIR=$WATCHDOG_DIR
PW_WATCHDOG_POLL_INTERVAL=0.5
PW_WATCHDOG_STDOUT=1
PW_WATCHDOG_LOG_MAX_SIZE=10485760
PW_WATCHDOG_LOG_BACKUPS=5
PW_WATCHDOG_USE_NETLINK=auto
EOF
    echo "Created .env file with default settings"
fi

echo ""
echo "========================================="
echo "Installation complete!"
echo "========================================="
echo ""
echo "Quick Start:"
echo ""
echo "1. Start the watchdog (if not using systemd):"
echo "   ./playwright_watchdog.py"
echo ""
echo "2. Run your tests:"
echo "   Node.js:  ./bin/pw-run.sh"
echo "   Python:   ./bin/pw-run-pytest.sh"
echo ""
echo "3. View logs:"
echo "   tail -f $WATCHDOG_DIR/logs/watchdog.jsonl"
echo ""
echo "4. Check CDP metadata:"
echo "   ls $WATCHDOG_DIR/cdp/"
echo ""
echo "For more information, see:"
echo "  - README.md for quick start"
echo "  - WATCHDOG_USAGE.md for detailed documentation"
echo "  - test_validation.md for validation tests"
echo ""


