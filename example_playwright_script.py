#!/usr/bin/env python3
"""
Example Playwright script to demonstrate the MiniAgent hook.
This script intentionally has errors to trigger support requests.

NO MODIFICATIONS NEEDED - the hook intercepts errors automatically!
"""
from playwright.sync_api import sync_playwright
import time

def login_flow_with_errors():
    """Simulates a login flow with multiple error scenarios."""
    print("=" * 60)
    print("Example Playwright Script (with intentional errors)")
    print("=" * 60)
    print()
    
    with sync_playwright() as p:
        # Launch browser (hook will inject debug port for Chromium)
        print("1. Launching browser...")
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        
        # Navigate to a demo site
        print("2. Navigating to demo site...")
        page.goto("https://example.com")
        print(f"   Current URL: {page.url}")
        print()
        
        # Error 1: Try to click a button that doesn't exist
        print("3. Attempting to click login button (doesn't exist)...")
        try:
            page.click("button:has-text('Login')", timeout=5000)
        except Exception as e:
            print(f"   ✗ Error caught: {type(e).__name__}")
            print(f"   → Support request sent automatically!")
            print()
        
        # Browser is still running!
        print("4. Browser still running, continuing...")
        time.sleep(2)
        
        # Error 2: Try to fill a field that doesn't exist
        print("5. Attempting to fill username field (doesn't exist)...")
        try:
            page.fill("input[name='username']", "testuser", timeout=3000)
        except Exception as e:
            print(f"   ✗ Error caught: {type(e).__name__}")
            print(f"   → Support request sent (or deduplicated if within cooldown)")
            print()
        
        # Still going!
        print("6. Still running, navigating to another page...")
        page.goto("https://playwright.dev")
        time.sleep(1)
        
        # Error 3: Assertion error
        print("7. Attempting an assertion that will fail...")
        try:
            from playwright.sync_api import expect
            expect(page.locator("h1")).to_have_text("This text doesn't exist", timeout=3000)
        except Exception as e:
            print(f"   ✗ Error caught: {type(e).__name__}")
            print(f"   → Support request sent!")
            print()
        
        # Final message
        print("8. All errors handled gracefully!")
        print("   - Browser is still open")
        print("   - Process didn't exit")
        print("   - Support requests sent to Flutter")
        print()
        print("Check your Flutter app for the support requests.")
        print()
        
        # Keep browser open for inspection
        print("Press Ctrl+C to close the browser...")
        try:
            time.sleep(60)
        except KeyboardInterrupt:
            print("\nClosing browser...")
        
        browser.close()
        print("\n✓ Script completed successfully!")

def successful_flow():
    """A flow with no errors to show normal operation."""
    print("=" * 60)
    print("Example: Successful Flow (no errors)")
    print("=" * 60)
    print()
    
    with sync_playwright() as p:
        print("1. Launching browser...")
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        print("2. Navigating to Playwright site...")
        page.goto("https://playwright.dev")
        
        print("3. Clicking 'Get Started' link...")
        page.click("text=Get started")
        
        print("4. Waiting for navigation...")
        page.wait_for_load_state("networkidle")
        
        print(f"5. Success! Current URL: {page.url}")
        print()
        print("✓ No errors, no support requests sent")
        
        time.sleep(2)
        browser.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "success":
        successful_flow()
    else:
        login_flow_with_errors()
        
        print()
        print("Try the successful flow with: python example_playwright_script.py success")



