# Changelog

All notable changes to the MiniAgent Playwright auto-hook system.

## [1.0.0] - 2025-10-27

### Initial Release

#### Added
- Auto-loaded `sitecustomize.py` hook for transparent Playwright error interception
- WebSocket client (`miniagent_ws.py`) with auto-reconnect and buffering
- Support for Chromium, Firefox, and WebKit browsers
- Automatic remote debugging port injection for Chromium-based browsers
- Deduplication and cooldown system to prevent spam
- Cross-platform support (Linux, Windows)
- Comprehensive documentation (README, QUICKSTART, ARCHITECTURE)
- Environment setup scripts for Linux and Windows
- Smoke tests for all browsers and error types
- Verification script to check setup

#### Features
- Zero-code-change integration with existing Playwright scripts
- Catches TimeoutError, Error, AssertionError exceptions
- Keeps browser and process running after errors
- Sends structured support requests to Flutter WebSocket server
- Browser-specific handling (debug port for Chromium, none for Firefox/WebKit)
- Configurable via environment variables
- Privacy controls (URL redaction)
- Thread-safe WebSocket communication
- Exponential backoff for reconnection (0.5s → 8s)

#### Components
- `sitecustomize.py`: Main hook, monkey-patches Playwright APIs
- `miniagent_ws.py`: WebSocket client and support request manager
- `setup_env.sh` / `setup_env.bat`: Environment configuration scripts
- `verify_setup.py`: Setup verification tool
- `example_playwright_script.py`: Demo script with intentional errors
- `tests/`: Smoke tests for Chromium, Firefox, WebKit, assertions, cooldown

#### Documentation
- `README.md`: Full user guide with setup and troubleshooting
- `QUICKSTART.md`: 5-minute setup guide
- `ARCHITECTURE.md`: Technical architecture and flow diagrams
- `tests/README.md`: Testing guide
- `.env.example`: Environment variable template

#### Configuration
- `MINIAGENT_ENABLED`: Enable/disable hook (default: 1)
- `MINIAGENT_WS_URL`: WebSocket server URL (default: ws://127.0.0.1:8777/ws)
- `MINIAGENT_TOKEN`: Shared authentication token (required)
- `MINIAGENT_CLIENT`: Client identifier (default: python-cdp-monitor)
- `MINIAGENT_COOLDOWN_SEC`: Cooldown period in seconds (default: 20)
- `MINIAGENT_REDACT_URLS`: Redact URLs/titles (default: 0)

#### Known Limitations
- Firefox and WebKit: No remote debugging port (limited remote control)
- DevToolsActivePort: 500ms delay after launch to ensure file is written
- Async API: Wrapper works but less tested than sync API
- macOS: Expected to work but not yet tested

## [Unreleased]

### Planned
- Optional screenshot capture on error
- HAR/network log collection
- Process heartbeat for "lost control" detection
- Configuration file support (.miniagent.toml)
- pytest plugin mode
- Multiple WebSocket servers (failover)
- Better async API support

### Under Consideration
- CDP-based page monitoring (separate from hook)
- Automatic trace collection
- Custom error classification rules
- Support for other testing frameworks (Selenium, Puppeteer)


