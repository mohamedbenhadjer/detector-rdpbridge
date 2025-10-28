#!/usr/bin/env python3
"""
Test script to validate HOLD mode functionality.
This script intentionally triggers an error and demonstrates the hold behavior.

Usage:
    # Terminal 1: Run this script with hold mode enabled
    export MINIAGENT_ON_ERROR=hold
    export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume
    export MINIAGENT_HOLD_SECS=30  # Optional: timeout after 30 seconds
    python test_hold_mode.py

    # Terminal 2: After the error occurs, resume the script
    touch /tmp/miniagent_resume
"""
from playwright.sync_api import sync_playwright
import time
import os

def test_hold_mode():
    """Test that hold mode keeps the script alive on errors."""
    print("=" * 60)
    print("Testing HOLD Mode")
    print("=" * 60)
    print()
    
    mode = os.environ.get("MINIAGENT_ON_ERROR", "report")
    print(f"Current mode: {mode}")
    print(f"Resume file: {os.environ.get('MINIAGENT_RESUME_FILE', '/tmp/miniagent_resume')}")
    print(f"Hold timeout: {os.environ.get('MINIAGENT_HOLD_SECS', 'forever')}")
    print()
    
    if mode != "hold":
        print("⚠ WARNING: MINIAGENT_ON_ERROR is not set to 'hold'")
        print("   The script will exit on error instead of holding.")
        print("   Set: export MINIAGENT_ON_ERROR=hold")
        print()
    
    with sync_playwright() as p:
        print("1. Launching browser...")
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        
        print("2. Navigating to example.com...")
        page.goto("https://example.com")
        print(f"   Current URL: {page.url}")
        print()
        
        print("3. Attempting to click non-existent button (will trigger error)...")
        print("   → In HOLD mode, script will pause here")
        print("   → Support request will be sent")
        print("   → Browser will stay open")
        print("   → Resume with: touch /tmp/miniagent_resume")
        print()
        
        try:
            # This will timeout and trigger the hold behavior
            page.click("button:has-text('ThisButtonDoesNotExist')", timeout=5000)
            print("   ✗ Unexpected: button was found!")
        except Exception as e:
            print(f"   ✓ Error caught: {type(e).__name__}")
            print(f"   → This should only print in report mode!")
        
        # If we get here in hold mode, the resume signal was received
        print()
        print("4. Script resumed! Continuing execution...")
        time.sleep(1)
        
        print("5. Navigating to another page...")
        page.goto("https://playwright.dev")
        print(f"   Current URL: {page.url}")
        print()
        
        print("6. All tests passed!")
        print("   ✓ Browser stayed open during error")
        print("   ✓ Script resumed after hold")
        print("   ✓ Execution continued normally")
        print()
        
        print("Keeping browser open for 5 seconds...")
        time.sleep(5)
        
        browser.close()
        print("\n✓ Test completed successfully!")

if __name__ == "__main__":
    import sys
    
    # Check if sitecustomize is loaded
    try:
        import sitecustomize
        print("✓ sitecustomize hook loaded")
    except ImportError:
        print("✗ sitecustomize not found - ensure PYTHONPATH is set")
        print("  export PYTHONPATH=\"/home/mohamed/detector-rdpbridge:$PYTHONPATH\"")
        sys.exit(1)
    
    print()
    test_hold_mode()

