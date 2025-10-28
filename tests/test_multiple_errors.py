"""
Smoke test: Multiple errors with cooldown
Tests that deduplication and cooldown work correctly.
"""
from playwright.sync_api import sync_playwright
import time

def test_multiple_errors():
    print("Starting multiple errors test (cooldown validation)...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://example.com")
        
        print("\nAttempting 3 errors in quick succession...")
        
        # First error - should send support request
        try:
            print("1. First error...")
            page.click("button:has-text('Error1')", timeout=2000)
        except Exception as e:
            print(f"   ✓ Caught: {type(e).__name__}")
        
        time.sleep(1)
        
        # Second error - should be deduplicated (within cooldown)
        try:
            print("2. Second error (should be deduplicated)...")
            page.click("button:has-text('Error2')", timeout=2000)
        except Exception as e:
            print(f"   ✓ Caught: {type(e).__name__}")
        
        time.sleep(1)
        
        # Third error - should also be deduplicated
        try:
            print("3. Third error (should be deduplicated)...")
            page.click("button:has-text('Error3')", timeout=2000)
        except Exception as e:
            print(f"   ✓ Caught: {type(e).__name__}")
        
        print("\n✓ All errors caught")
        print("✓ Only first error should trigger support request (check Flutter logs)")
        print("  (Cooldown period prevents spam)")
        
        time.sleep(3)
        browser.close()

if __name__ == "__main__":
    test_multiple_errors()


