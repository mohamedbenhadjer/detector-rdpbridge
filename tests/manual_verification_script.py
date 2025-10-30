"""
Manual verification script: Test both Page and Locator errors with Flutter
Run this with the Flutter app running to verify CDP criteria are sent correctly.

Expected Flutter logs should show:
- First error: controlTarget with debugPort, urlContains, titleContains (Page error)
- Second error: controlTarget with debugPort, urlContains, titleContains (Locator error)
- Both should connect to the correct CDP tab on Pixilart

Usage:
    export MINIAGENT_ENABLED=1
    export MINIAGENT_TOKEN=your_token_here
    python tests/manual_verification_script.py
"""
from playwright.sync_api import sync_playwright
import time

def main():
    print("="*60)
    print("Manual Verification: Page vs Locator Errors")
    print("="*60)
    print("\nEnsure Flutter app is running on ws://127.0.0.1:8777/ws")
    print("Watch Flutter logs for CDP connection details\n")
    
    with sync_playwright() as p:
        # Launch Chromium with debug port
        print("[1] Launching Chromium...")
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Navigate to Pixilart (matching the user's logs)
        print("[2] Navigating to Pixilart...")
        page.goto("https://www.pixilart.com/", wait_until="domcontentloaded")
        print(f"    URL: {page.url}")
        print(f"    Title: {page.title()}")
        
        time.sleep(2)
        
        # Test 1: Page method error
        print("\n[3] Testing Page.wait_for_selector error...")
        print("    Expected: Flutter logs show debugPort=9222, urlContains, titleContains")
        try:
            page.wait_for_selector("canvas.non-existent-element", timeout=3000)
        except Exception as e:
            print(f"    ✓ Caught: {type(e).__name__}")
        
        time.sleep(3)
        print("    Check Flutter logs for first support_request with full controlTarget")
        
        # Test 2: Locator method error (the fix being tested)
        print("\n[4] Testing Locator.click error...")
        print("    Expected: Flutter logs show debugPort=9222, urlContains, titleContains")
        try:
            locator = page.locator("button:has-text('NonExistentStartDrawingButton')")
            locator.click(timeout=3000)
        except Exception as e:
            print(f"    ✓ Caught: {type(e).__name__}")
        
        time.sleep(3)
        print("    Check Flutter logs for second support_request with full controlTarget")
        
        print("\n[5] Verification checklist:")
        print("    □ First request has debugPort: 9222")
        print("    □ First request has urlContains: https://www.pixilart.com/")
        print("    □ First request has titleContains: Pixilart...")
        print("    □ Second request has debugPort: 9222")
        print("    □ Second request has urlContains: https://www.pixilart.com/")
        print("    □ Second request has titleContains: Pixilart...")
        print("    □ Both requests connected to correct CDP tab (not random window)")
        
        print("\n[6] Keeping browser open for 10 seconds...")
        print("    Verify in Flutter that CDP connected to Pixilart tab both times")
        time.sleep(10)
        
        browser.close()
        print("\n✓ Manual verification completed")
        print("  Review Flutter logs to confirm both errors included CDP criteria\n")

if __name__ == "__main__":
    main()

