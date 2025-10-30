#!/usr/bin/env python3
"""
Verify that MiniAgent is correctly configured.
Run this before using the hook to ensure everything is set up properly.
"""
import os
import sys

def check_mark(condition, message):
    """Print a check mark or X based on condition."""
    if condition:
        print(f"✓ {message}")
        return True
    else:
        print(f"✗ {message}")
        return False

def main():
    print("=" * 60)
    print("MiniAgent Setup Verification")
    print("=" * 60)
    print()
    
    all_ok = True
    
    # Check PYTHONPATH
    print("1. Checking PYTHONPATH...")
    expected_dir = "/home/mohamed/detector-rdpbridge"
    in_path = any(expected_dir in p for p in sys.path)
    all_ok &= check_mark(in_path, f"'{expected_dir}' in PYTHONPATH")
    if not in_path:
        print(f"   → Add to PYTHONPATH: export PYTHONPATH=\"{expected_dir}:$PYTHONPATH\"")
    print()
    
    # Check if sitecustomize can be imported
    print("2. Checking sitecustomize hook...")
    try:
        import sitecustomize
        all_ok &= check_mark(True, "sitecustomize.py can be imported")
    except ImportError as e:
        all_ok &= check_mark(False, f"sitecustomize.py import failed: {e}")
        print(f"   → Ensure PYTHONPATH includes this directory")
    print()
    
    # Check miniagent_ws
    print("3. Checking miniagent_ws module...")
    try:
        import miniagent_ws
        all_ok &= check_mark(True, "miniagent_ws.py can be imported")
    except ImportError as e:
        all_ok &= check_mark(False, f"miniagent_ws.py import failed: {e}")
    print()
    
    # Check dependencies
    print("4. Checking dependencies...")
    try:
        import websocket
        all_ok &= check_mark(True, "websocket-client installed")
    except ImportError:
        all_ok &= check_mark(False, "websocket-client not installed")
        print("   → Install: pip install websocket-client")
    
    try:
        from playwright.sync_api import sync_playwright
        all_ok &= check_mark(True, "playwright installed")
    except ImportError:
        all_ok &= check_mark(False, "playwright not installed")
        print("   → Install: pip install playwright && playwright install")
    print()
    
    # Check environment variables
    print("5. Checking environment variables...")
    
    enabled = os.environ.get("MINIAGENT_ENABLED", "1")
    all_ok &= check_mark(enabled == "1", f"MINIAGENT_ENABLED={enabled}")
    if enabled != "1":
        print("   → Enable: export MINIAGENT_ENABLED=1")
    
    ws_url = os.environ.get("MINIAGENT_WS_URL", "")
    has_url = bool(ws_url)
    all_ok &= check_mark(has_url, f"MINIAGENT_WS_URL={ws_url or '(not set)'}")
    if not has_url:
        print("   → Set: export MINIAGENT_WS_URL=\"ws://127.0.0.1:8777/ws\"")
    
    token = os.environ.get("MINIAGENT_TOKEN", "")
    has_token = bool(token)
    all_ok &= check_mark(has_token, f"MINIAGENT_TOKEN={'***set***' if has_token else '(not set)'}")
    if not has_token:
        print("   → Set: export MINIAGENT_TOKEN=\"your-shared-token-from-flutter\"")
    
    client = os.environ.get("MINIAGENT_CLIENT", "python-cdp-monitor")
    all_ok &= check_mark(True, f"MINIAGENT_CLIENT={client}")
    
    cooldown = os.environ.get("MINIAGENT_COOLDOWN_SEC", "20")
    all_ok &= check_mark(True, f"MINIAGENT_COOLDOWN_SEC={cooldown}")
    
    print()
    
    # Try to initialize the support manager
    print("6. Testing WebSocket client initialization...")
    if has_token:
        try:
            from miniagent_ws import get_support_manager
            manager = get_support_manager()
            if manager:
                all_ok &= check_mark(True, f"Support manager initialized (runId: {manager.run_id})")
                print("   Note: WebSocket connection happens in background")
            else:
                all_ok &= check_mark(False, "Support manager failed to initialize")
        except Exception as e:
            all_ok &= check_mark(False, f"Error initializing manager: {e}")
    else:
        print("   ⊘ Skipped (token not set)")
    print()
    
    # Optional: HTTP resume endpoint configuration
    print("7. Checking HTTP resume endpoint (optional)...")
    resume_http = os.environ.get("MINIAGENT_RESUME_HTTP", "0")
    if resume_http == "1":
        host = os.environ.get("MINIAGENT_RESUME_HTTP_HOST", "127.0.0.1")
        port = os.environ.get("MINIAGENT_RESUME_HTTP_PORT", "8787")
        http_token = os.environ.get("MINIAGENT_RESUME_HTTP_TOKEN", "")
        _ = check_mark(True, f"MINIAGENT_RESUME_HTTP=1 (enabled)")
        _ = check_mark(bool(host), f"MINIAGENT_RESUME_HTTP_HOST={host}")
        _ = check_mark(bool(port), f"MINIAGENT_RESUME_HTTP_PORT={port}")
        if http_token:
            _ = check_mark(True, "MINIAGENT_RESUME_HTTP_TOKEN=***set***")
        else:
            _ = check_mark(False, "MINIAGENT_RESUME_HTTP_TOKEN not set (required when enabled)")
        print("   Resume file:", os.environ.get("MINIAGENT_RESUME_FILE", "/tmp/miniagent_resume"))
    else:
        _ = check_mark(True, "MINIAGENT_RESUME_HTTP=0 (disabled)")
    print()
    
    # Summary
    print("=" * 60)
    if all_ok:
        print("✓ All checks passed! MiniAgent is ready to use.")
        print()
        print("Next steps:")
        print("  1. Start your Flutter app with the WebSocket server")
        print("  2. Run a test: python tests/test_chromium_timeout.py")
        print("  3. Or run your own Playwright scripts: python my_script.py")
    else:
        print("✗ Some checks failed. Please fix the issues above.")
        print()
        print("Quick fix:")
        print("  source setup_env.sh  # Linux/Mac")
        print("  setup_env.bat        # Windows")
        print("  export MINIAGENT_TOKEN=\"your-token\"")
    print("=" * 60)
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())



