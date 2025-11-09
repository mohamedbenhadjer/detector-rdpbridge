#!/usr/bin/env python3
"""
Async test for popup prevention functionality.
"""
from playwright.async_api import async_playwright
import asyncio
import os

# Enable popup prevention logging
os.environ["MINIAGENT_PREVENT_TABS_LOG"] = "1"

async def test_popup_prevention_async():
    """Test that popups/new tabs are prevented in async API."""
    print("=" * 70)
    print("   POPUP PREVENTION - ASYNC TEST")
    print("=" * 70)
    print()
    
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context()
        page = await context.new_page()
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
        await page.goto("https://example.com")
        print(f"   Initial page count: {len(context.pages)}")
        
        # Execute window.open() - should NOT create a new tab
        print("   Calling window.open('https://www.google.com', '_blank')...")
        try:
            await page.evaluate("window.open('https://www.google.com', '_blank')")
            await asyncio.sleep(2)
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
        await page.goto("https://example.com")
        await asyncio.sleep(1)
        
        # Test target="_blank" link
        print("TEST 2: Testing link with target='_blank'...")
        print(f"   Initial page count: {len(context.pages)}")
        
        # Create and click a _blank link
        print("   Creating link with target='_blank' and clicking it...")
        try:
            await page.evaluate("""
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
            await asyncio.sleep(2)
        except Exception as e:
            print(f"   (Navigation may have occurred: {type(e).__name__})")
        
        final_page_count = len(context.pages)
        print(f"   Final page count: {final_page_count}")
        
        if final_page_count == 1:
            print("   ✓ PASS: No new tab created!")
        else:
            print(f"   ✗ FAIL: {final_page_count} total pages exist")
        print()
        
        # Test multiple simultaneous window.open() calls
        print("TEST 3: Testing multiple window.open() calls...")
        await page.goto("https://example.com")
        await asyncio.sleep(1)
        print(f"   Initial page count: {len(context.pages)}")
        
        print("   Calling window.open() 3 times...")
        try:
            await page.evaluate("""
                () => {
                    window.open('https://www.example.com', '_blank');
                    window.open('https://www.example.org', '_blank');
                    window.open('https://www.example.net', '_blank');
                }
            """)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"   (Navigation may have occurred: {type(e).__name__})")
        
        final_page_count = len(context.pages)
        print(f"   Final page count: {final_page_count}")
        
        if final_page_count == 1:
            print("   ✓ PASS: Still only 1 page!")
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
            print("   ✓✓✓ SUCCESS: Async popup prevention is working! ✓✓✓")
            print("   No new tabs or popups were created.")
        else:
            print()
            print("   ✗✗✗ FAILURE: Popups were created ✗✗✗")
        
        print()
        print("Keeping browser open for 3 seconds...")
        await asyncio.sleep(3)
        
        await browser.close()
        print("✓ Browser closed")
        print()
        
        print("=" * 70)
        print("   TEST COMPLETED")
        print("=" * 70)
        
        return len(new_pages_created) == 0

if __name__ == "__main__":
    success = asyncio.run(test_popup_prevention_async())
    exit(0 if success else 1)

