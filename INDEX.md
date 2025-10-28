# MiniAgent Documentation Index

Quick navigation to all documentation and resources.

## 🚀 Getting Started (Read These First)

1. **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup guide
   - Install dependencies
   - Set environment variables
   - Verify installation
   - Run first test

2. **[README.md](README.md)** - Complete user guide
   - Features and how it works
   - Detailed setup instructions (Linux/Windows)
   - Configuration reference
   - Troubleshooting basics

3. **[verify_setup.py](verify_setup.py)** - Setup verification tool
   - Run: `python verify_setup.py`
   - Checks all prerequisites
   - Validates configuration

## 📖 Documentation

### User Guides
- **[README.md](README.md)** - Main user documentation
- **[QUICKSTART.md](QUICKSTART.md)** - Fast setup guide
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions
- **[tests/README.md](tests/README.md)** - Testing guide

### Technical Documentation
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Technical deep-dive
  - Component architecture
  - Flow diagrams
  - Threading model
  - Security and performance
  - Extension points

- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Project overview
  - Problem statement
  - Solution approach
  - Key features
  - Use cases

- **[CHANGELOG.md](CHANGELOG.md)** - Version history
  - Current version: 1.0.0
  - Feature list
  - Known limitations

## 🔧 Setup Files

### Environment Configuration
- **[.env.example](.env.example)** - Environment variable template
- **[setup_env.sh](setup_env.sh)** - Linux/Mac setup script
- **[setup_env.bat](setup_env.bat)** - Windows setup script

### Dependencies
- **[requirements.txt](requirements.txt)** - Python dependencies
  - playwright>=1.40.0
  - websocket-client>=1.6.0

## 💻 Core Code

### Main Components
- **[sitecustomize.py](sitecustomize.py)** - Auto-loaded hook
  - Monkey-patches Playwright
  - Injects remote debugging flags
  - Catches and reports exceptions

- **[miniagent_ws.py](miniagent_ws.py)** - WebSocket client
  - MiniAgentWSClient: Connection management
  - SupportRequestManager: Request handling

### Examples
- **[example_playwright_script.py](example_playwright_script.py)** - Demo script
  - Shows intentional errors
  - Demonstrates error handling
  - Browser stays open

## 🧪 Tests

### Smoke Tests (in tests/ directory)
- **[test_chromium_timeout.py](tests/test_chromium_timeout.py)** - Chromium test
- **[test_firefox_timeout.py](tests/test_firefox_timeout.py)** - Firefox test
- **[test_webkit_timeout.py](tests/test_webkit_timeout.py)** - WebKit test
- **[test_multiple_errors.py](tests/test_multiple_errors.py)** - Cooldown test
- **[test_assertion_error.py](tests/test_assertion_error.py)** - Assertion test

Run all:
```bash
cd tests
for test in test_*.py; do python $test; done
```

## 📋 Quick Reference

### Setup Commands

**Linux/Mac:**
```bash
# One-time setup
cd /home/mohamed/detector-rdpbridge
pip install -r requirements.txt
playwright install chromium
source setup_env.sh
export MINIAGENT_TOKEN="your-token"

# Verify
python verify_setup.py

# Test
python tests/test_chromium_timeout.py
```

**Windows (PowerShell):**
```powershell
# One-time setup
cd C:\Users\YourUser\detector-rdpbridge
pip install -r requirements.txt
playwright install chromium
.\setup_env.bat
$env:MINIAGENT_TOKEN = "your-token"

# Verify
python verify_setup.py

# Test
python tests\test_chromium_timeout.py
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PYTHONPATH` | ✅ Yes | - | Must include project directory |
| `MINIAGENT_TOKEN` | ✅ Yes | - | Shared auth token |
| `MINIAGENT_ENABLED` | No | 1 | Enable/disable hook |
| `MINIAGENT_WS_URL` | No | ws://127.0.0.1:8777/ws | WebSocket server |
| `MINIAGENT_CLIENT` | No | python-cdp-monitor | Client name |
| `MINIAGENT_COOLDOWN_SEC` | No | 20 | Dedup cooldown |
| `MINIAGENT_REDACT_URLS` | No | 0 | Redact URLs/titles |

### File Structure

```
detector-rdpbridge/
├── Core
│   ├── sitecustomize.py          # Auto-loaded hook
│   ├── miniagent_ws.py            # WebSocket client
│   └── requirements.txt           # Dependencies
│
├── Setup
│   ├── setup_env.sh               # Linux/Mac setup
│   ├── setup_env.bat              # Windows setup
│   ├── .env.example               # Env template
│   └── verify_setup.py            # Verification tool
│
├── Documentation
│   ├── README.md                  # Main guide
│   ├── QUICKSTART.md              # 5-min setup
│   ├── ARCHITECTURE.md            # Technical docs
│   ├── TROUBLESHOOTING.md         # Common issues
│   ├── PROJECT_SUMMARY.md         # Overview
│   ├── CHANGELOG.md               # Version history
│   └── INDEX.md                   # This file
│
├── Examples
│   └── example_playwright_script.py
│
└── Tests
    ├── test_chromium_timeout.py
    ├── test_firefox_timeout.py
    ├── test_webkit_timeout.py
    ├── test_multiple_errors.py
    ├── test_assertion_error.py
    └── README.md
```

## 🔍 Common Tasks

### First-Time Setup
1. Read [QUICKSTART.md](QUICKSTART.md)
2. Run setup script: `source setup_env.sh` (Linux) or `setup_env.bat` (Windows)
3. Set token: `export MINIAGENT_TOKEN="..."`
4. Verify: `python verify_setup.py`
5. Test: `python tests/test_chromium_timeout.py`

### Troubleshooting
1. Run: `python verify_setup.py`
2. Check: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. Enable debug: `export LOGGING_LEVEL=DEBUG`
4. Check Flutter logs

### Understanding Architecture
1. Read [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - High-level overview
2. Read [ARCHITECTURE.md](ARCHITECTURE.md) - Technical details
3. Review [sitecustomize.py](sitecustomize.py) - Hook implementation
4. Review [miniagent_ws.py](miniagent_ws.py) - WebSocket client

### Running Tests
1. Read [tests/README.md](tests/README.md)
2. Start Flutter app
3. Run individual test: `python tests/test_chromium_timeout.py`
4. Or run all: `cd tests && for t in test_*.py; do python $t; done`

### Using with Your Scripts
**No setup needed!** Just run:
```bash
python your_playwright_script.py
```

The hook automatically:
- Detects errors
- Sends support requests
- Keeps browser open
- Enables remote debugging (Chromium)

## 🆘 Getting Help

### Check This First
1. ✅ [QUICKSTART.md](QUICKSTART.md) - Is setup complete?
2. ✅ [verify_setup.py](verify_setup.py) - Does verification pass?
3. ✅ [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Is your issue listed?
4. ✅ [README.md](README.md) - Check configuration section

### Debug Steps
1. Run `python verify_setup.py`
2. Check environment: `echo $MINIAGENT_TOKEN`
3. Check PYTHONPATH: `python -c "import sys; print(sys.path)"`
4. Test hook load: `python -c "import sitecustomize; print('OK')"`
5. Enable debug logging (see TROUBLESHOOTING.md)
6. Check Flutter logs

## 📊 Project Stats

- **Lines of Code**: ~550 (sitecustomize.py + miniagent_ws.py)
- **Documentation**: ~3500 lines across 8 files
- **Tests**: 5 smoke tests
- **Setup Time**: ~5 minutes
- **Overhead**: <200ms startup, ~0ms runtime

## 🎯 Next Steps

### New Users
1. ✅ Read [QUICKSTART.md](QUICKSTART.md)
2. ✅ Follow setup steps
3. ✅ Run `verify_setup.py`
4. ✅ Run a test from tests/
5. ✅ Try [example_playwright_script.py](example_playwright_script.py)
6. ✅ Use with your own scripts (no changes needed!)

### Developers
1. Read [ARCHITECTURE.md](ARCHITECTURE.md)
2. Review core code (sitecustomize.py, miniagent_ws.py)
3. Understand flow diagrams
4. Check extension points
5. Review tests for examples

### Troubleshooting
1. Run [verify_setup.py](verify_setup.py)
2. Read [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. Enable debug logging
4. Check specific section for your issue

---

**Quick Links:**
- 🚀 [Get Started](QUICKSTART.md)
- 📖 [Full Docs](README.md)
- 🔧 [Architecture](ARCHITECTURE.md)
- 🐛 [Troubleshooting](TROUBLESHOOTING.md)
- ✅ [Verify Setup](verify_setup.py)
- 🧪 [Run Tests](tests/README.md)



