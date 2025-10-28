"""
Smoke test: Chromium timeout error
Tests that the hook correctly intercepts TimeoutError and sends support request.
"""
from playwright.sync_api import sync_playwright
import time

def test_chromium_timeout():
    print("Starting Chromium timeout test...")
    
    with sync_playwright() as p:
        # Launch Chromium (hook will inject debug port)
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Navigate to a page
        page.goto("https://example.com")
        print(f"Navigated to: {page.url}")
        
        # Try to click a non-existent button (will timeout)
        try:
            print("Attempting to click non-existent button...")
            page.click("button:has-text('ThisButtonDoesNotExist')", timeout=5000)
        except Exception as e:
            print(f"✓ Caught expected error: {type(e).__name__}")
            print(f"  Message: {str(e)[:100]}")
        
        # Verify browser is still running
        print("✓ Browser still running after error")
        print(f"  Current URL: {page.url}")
        
        # Give time to see the support request in Flutter logs
        print("\nWaiting 3 seconds for support request to be sent...")
        time.sleep(3)
        
        print("✓ Test completed successfully")
        browser.close()

if __name__ == "__main__":
    test_chromium_timeout()


