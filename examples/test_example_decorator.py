"""
Example: Using the decorator for error reporting.

This test demonstrates the decorator form of report_errors_to_flutter.
The decorator auto-detects the 'page' fixture and reports errors to Flutter.
"""

import pytest
from pw_ws_reporter import report_errors_to_flutter


# Example 1: Basic decorator usage
@report_errors_to_flutter(description_hint="Login flow failed")
async def test_login_with_decorator(page):
    """
    Test login flow with automatic error reporting.
    
    If this test fails, the decorator will:
    1. Capture the page URL and title
    2. Extract CDP targetId (if Chromium)
    3. Send a support request to Flutter
    4. Log the outcome
    """
    await page.goto("https://example.com/login")
    await page.fill("#username", "testuser")
    await page.fill("#password", "testpass")
    await page.click("#submit")
    
    # This will fail and trigger error reporting
    await page.wait_for_selector("#dashboard", timeout=5000)


# Example 2: Decorator without description hint
@report_errors_to_flutter()
async def test_checkout_with_decorator(page):
    """
    Test checkout with decorator but no custom hint.
    
    The error description will just be the exception message.
    """
    await page.goto("https://example.com/checkout")
    await page.click("#complete-order")
    
    # Simulate a failure
    raise AssertionError("Order confirmation not displayed")


# Example 3: Multiple test steps with decorator
@report_errors_to_flutter(description_hint="Search functionality test failed")
async def test_search_with_decorator(page):
    """
    Test search with multiple steps.
    
    Any failure in any step will be reported with the hint.
    """
    await page.goto("https://example.com")
    await page.fill("#search", "playwright")
    await page.click("#search-button")
    await page.wait_for_selector(".search-results")
    
    results = await page.locator(".result-item").count()
    assert results > 0, "No search results found"


# Example 4: Test that passes (no error report sent)
@report_errors_to_flutter(description_hint="This won't be sent")
async def test_passing_test(page):
    """
    Test that passes normally.
    
    Since this test doesn't fail, no error report is sent.
    """
    await page.goto("https://example.com")
    title = await page.title()
    assert "Example" in title

