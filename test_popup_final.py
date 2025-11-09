#!/usr/bin/env python3
"""
Final test for popup prevention - verifies no new tabs are created.
"""
from playwright.sync_api import sync_playwright
import time
import os

# Enable popup prevention logging
os.environ["MINIAGENT_PREVENT_TABS_LOG"] = "1"

def test_popup_prevention_final():
    """Test that popups/new tabs are prevented."""
    print("=" * 70)
    print("   POPUP PREVENTION - FINAL TEST")
    print("=" * 70)
    print()
    
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context()
        page = context.new_page()
        print(f"✓ Browser launched with {len(context.pages)} page(s)")
        print()
        
        # Track new pages
        new_pages_created = []
        
        def on_page(new_page):
            new_pages_created.append(new_page)
            print(f"   ⚠ NEW PAGE DETECTED! Total: {len(new_pages_created)}")
            print(f"      URL: {new_page.url}")
        
        context.on("page", on_page)
        
        # Navigate to example.com
        print("TEST 1: Testing window.open()...")
        page.goto("https://example.com")
        print(f"   Initial page count: {len(context.pages)}")
        
        # Execute window.open() - should NOT create a new tab
        print("   Calling window.open('https://www.google.com', '_blank')...")
        try:
            page.evaluate("window.open('https://www.google.com', '_blank')")
            time.sleep(2)
        except Exception as e:
            print(f"   (Navigation may have occurred: {type(e).__name__})")
        
        final_page_count = len(context.pages)
        print(f"   Final page count: {final_page_count}")
        
        if final_page_count == 1:
            print("   ✓ PASS: No new tab created!")
        else:
            print(f"   ✗ FAIL: {final_page_count} total pages exist")
        print()
        
        # Reset to example.com
        page.goto("https://example.com")
        time.sleep(1)
        
        # Test target="_blank" link
        print("TEST 2: Testing link with target='_blank'...")
        print(f"   Initial page count: {len(context.pages)}")
        
        # Create and click a _blank link
        print("   Creating link with target='_blank' and clicking it...")
        try:
            page.evaluate("""
                () => {
                    const link = document.createElement('a');
                    link.href = 'https://www.example.org';
                    link.target = '_blank';
                    link.id = 'test-link';
                    link.textContent = 'Test';
                    document.body.appendChild(link);
                    link.click();
                }
            """)
            time.sleep(2)
        except Exception as e:
            print(f"   (Navigation may have occurred: {type(e).__name__})")
        
        final_page_count = len(context.pages)
        print(f"   Final page count: {final_page_count}")
        
        if final_page_count == 1:
            print("   ✓ PASS: No new tab created!")
        else:
            print(f"   ✗ FAIL: {final_page_count} total pages exist")
        print()
        
        # Summary
        print("-" * 70)
        print("SUMMARY:")
        print(f"   • New pages/tabs created: {len(new_pages_created)}")
        print(f"   • Final page count in context: {len(context.pages)}")
        
        if len(new_pages_created) == 0:
            print()
            print("   ✓✓✓ SUCCESS: Popup prevention is working! ✓✓✓")
            print("   No new tabs or popups were created.")
        else:
            print()
            print("   ✗✗✗ FAILURE: Popups were created ✗✗✗")
        
        print()
        print("Keeping browser open for 3 seconds...")
        time.sleep(3)
        
        browser.close()
        print("✓ Browser closed")
        print()
        
        print("=" * 70)
        print("   TEST COMPLETED")
        print("=" * 70)
        
        return len(new_pages_created) == 0

if __name__ == "__main__":
    success = test_popup_prevention_final()
    exit(0 if success else 1)

