# Installation Guide

This guide covers different installation methods for the Playwright Watchdog based on your Python environment.

## Prerequisites

- Python 3.7 or later
- Node.js (for Node.js Playwright projects)
- Playwright (Node.js or Python version)

## Installation Methods

### Method 1: Using Virtual Environment (Recommended)

This is the cleanest approach and works with all Python installations:

```bash
# Create a virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run the watchdog
./playwright_watchdog.py
```

### Method 2: System Packages (Debian/Ubuntu)

If you're on Debian/Ubuntu and prefer system packages:

```bash
# Install required system packages
sudo apt update
sudo apt install python3-psutil python3-dotenv

# Optional: Install python3-pyroute2 for netlink support (requires root)
# sudo apt install python3-pyroute2

# Run the watchdog directly
./playwright_watchdog.py
```

### Method 3: Using pipx (Isolated Installation)

For a system-wide isolated installation:

```bash
# Install pipx if not already installed
sudo apt install pipx
# or
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Note: pipx is typically for applications, not libraries
# You'll need to create a wrapper script

# Instead, use --break-system-packages (not recommended)
pip install -r requirements.txt --break-system-packages
```

### Method 4: User Installation (Older Systems)

On systems without external management restrictions:

```bash
pip install -r requirements.txt --user

# Make sure ~/.local/bin is in your PATH
export PATH="$HOME/.local/bin:$PATH"

# Run the watchdog
./playwright_watchdog.py
```

## Quick Install Script

Use the provided installation script:

```bash
./install.sh
```

This script will:
1. Detect your OS
2. Install Python dependencies (via pip or system packages)
3. Create necessary directories
4. Make scripts executable
5. Optionally set up systemd service (Linux)

## Verifying Installation

Run the smoke test to verify everything is working:

```bash
./smoke_test.sh
```

This will check:
- Python dependencies
- Script files and permissions
- Core functionality
- Injector syntax

## Minimal Dependencies

If you can't install all dependencies, here's what's strictly required:

### Core (Required)
- `psutil` - Process monitoring

### Optional
- `python-dotenv` - .env file support (can use shell exports instead)
- `pywin32` - Windows WMI support (falls back to polling)
- `pyroute2` - Linux netlink support (falls back to polling)

To run with minimal dependencies:

```bash
# Install only psutil via system package
sudo apt install python3-psutil

# Or in a venv
python3 -m venv venv
source venv/bin/activate
pip install psutil

# Run the watchdog
./playwright_watchdog.py
```

## Platform-Specific Notes

### Linux

**systemd Service:**
```bash
# Edit paths in service file
vi systemd/user/pw-watchdog.service

# Install
mkdir -p ~/.config/systemd/user
cp systemd/user/pw-watchdog.service ~/.config/systemd/user/
systemctl --user enable --now pw-watchdog
```

**Netlink Support (Optional):**
For event-driven process tracking (requires root):
```bash
sudo apt install python3-pyroute2
# Then run watchdog as root or with CAP_NET_ADMIN
```

### Windows

**Install Python Dependencies:**
```powershell
pip install -r requirements.txt
```

**Install as Scheduled Task:**
```powershell
powershell -ExecutionPolicy Bypass -File .\windows\install_watchdog_task.ps1
```

### macOS

Same as Linux, but no systemd service. Run manually or use launchd.

## Troubleshooting

### "externally-managed-environment" Error

Your Python installation is managed by your OS package manager. Solutions:

1. **Use a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Install system packages**:
   ```bash
   sudo apt install python3-psutil python3-dotenv
   ```

3. **Override** (not recommended):
   ```bash
   pip install -r requirements.txt --break-system-packages
   ```

### Permission Errors

If you get permission errors when creating directories:

```bash
# Ensure the watchdog directory is writable
mkdir -p ~/.pw_watchdog
chmod 755 ~/.pw_watchdog
```

### Module Not Found

If the watchdog can't find modules:

```bash
# Ensure you're using the same Python that has the modules
which python3
python3 -m pip list | grep psutil

# Or activate your venv
source venv/bin/activate
```

### systemd Service Won't Start

Check the service status and logs:

```bash
systemctl --user status pw-watchdog
journalctl --user -u pw-watchdog -n 50
```

Common issues:
- Incorrect paths in service file
- Python interpreter not found
- Dependencies not installed for the user running the service

## Next Steps

After installation:

1. **Start the watchdog:**
   ```bash
   ./playwright_watchdog.py
   ```

2. **Run a test:**
   ```bash
   # Node.js
   ./bin/pw-run.sh

   # Python
   ./bin/pw-run-pytest.sh
   ```

3. **Check the logs:**
   ```bash
   tail -f ~/.pw_watchdog/logs/watchdog.jsonl
   ```

4. **View CDP metadata:**
   ```bash
   cat ~/.pw_watchdog/cdp/*.json
   ```

For detailed usage, see [WATCHDOG_USAGE.md](WATCHDOG_USAGE.md).


