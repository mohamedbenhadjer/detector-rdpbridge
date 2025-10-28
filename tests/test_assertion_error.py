"""
Smoke test: Assertion error with expect()
Tests that the hook catches Playwright assertion failures.
"""
from playwright.sync_api import sync_playwright, expect
import time

def test_assertion_error():
    print("Starting assertion error test...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://example.com")
        
        # Try an assertion that will fail
        try:
            print("Attempting assertion that will fail...")
            expect(page.locator("h1")).to_have_text("This text does not exist", timeout=3000)
        except Exception as e:
            print(f"✓ Caught expected error: {type(e).__name__}")
            print(f"  Message: {str(e)[:100]}")
        
        print("✓ Browser still running after assertion error")
        
        time.sleep(3)
        browser.close()

if __name__ == "__main__":
    test_assertion_error()



