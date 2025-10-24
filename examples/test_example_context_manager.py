"""
Example: Using the context manager for error reporting.

This test demonstrates the context manager form, which gives fine-grained
control over which sections of a test should report errors.
"""

import pytest
from pw_ws_reporter import report_errors_to_flutter


# Example 1: Basic context manager usage
async def test_login_with_context_manager(page):
    """
    Test login with context manager for specific section.
    
    Only errors within the 'async with' block are reported.
    """
    await page.goto("https://example.com")
    
    # Setup steps - errors here won't be reported
    await page.click("#login-button")
    
    # Critical section - errors here will be reported
    async with report_errors_to_flutter(page, description_hint="Login form submission failed"):
        await page.fill("#username", "testuser")
        await page.fill("#password", "testpass")
        await page.click("#submit")
        
        # This will fail and trigger reporting
        await page.wait_for_selector("#dashboard", timeout=5000)


# Example 2: Multiple context managers in one test
async def test_checkout_flow_with_multiple_contexts(page):
    """
    Test with multiple critical sections, each with its own error reporting.
    """
    await page.goto("https://example.com/shop")
    
    # First critical section: Adding to cart
    async with report_errors_to_flutter(page, description_hint="Failed to add item to cart"):
        await page.click(".product:first-child .add-to-cart")
        await page.wait_for_selector(".cart-badge")
    
    # Second critical section: Checkout
    async with report_errors_to_flutter(page, description_hint="Failed during checkout"):
        await page.click("#cart-icon")
        await page.click("#checkout")
        await page.fill("#cc-number", "4242424242424242")
        await page.click("#complete-order")
        
        # This might fail
        await page.wait_for_selector("#order-confirmation", timeout=5000)


# Example 3: Context manager with no description hint
async def test_search_with_context_manager(page):
    """
    Test search with context manager but no custom hint.
    """
    await page.goto("https://example.com")
    
    async with report_errors_to_flutter(page):
        await page.fill("#search", "test query")
        await page.click("#search-button")
        await page.wait_for_selector(".search-results")


# Example 4: Nested operations with selective reporting
async def test_selective_error_reporting(page):
    """
    Test where only specific operations are monitored.
    
    This demonstrates fine control over what gets reported.
    """
    await page.goto("https://example.com")
    
    # Navigation errors won't be reported
    await page.click("#nav-menu")
    
    # But form submission errors will be
    async with report_errors_to_flutter(page, description_hint="Form submission failed"):
        await page.fill("#feedback", "This is a test")
        await page.click("#submit-feedback")
        
        # Wait for success message
        await page.wait_for_selector(".success-message", timeout=3000)
    
    # Cleanup errors also won't be reported
    await page.click("#close")

