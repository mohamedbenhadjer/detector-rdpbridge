"""
Example: Automatic error reporting via pytest plugin.

These tests don't use any decorators or context managers.
The pytest plugin automatically detects failures and reports them to Flutter.

To use this, just run:
    pytest examples/test_example_auto_plugin.py -v

Or via the CLI:
    pw-ws-reporter run pytest examples/test_example_auto_plugin.py -v
"""

import pytest


# Example 1: Simple test with page fixture
async def test_login_auto(page):
    """
    Test that will automatically report errors via the pytest plugin.
    
    The plugin detects:
    - Test failure
    - The 'page' fixture
    - Extracts URL, title, targetId
    - Sends support request
    """
    await page.goto("https://example.com/login")
    await page.fill("#username", "testuser")
    await page.fill("#password", "wrongpass")
    await page.click("#submit")
    
    # This will fail
    await page.wait_for_selector(".error-message", timeout=5000)
    error_text = await page.locator(".error-message").text_content()
    assert "Invalid credentials" in error_text


# Example 2: Test with assertion failure
async def test_checkout_auto(page):
    """
    Test with assertion failure - also reported automatically.
    """
    await page.goto("https://example.com/checkout")
    
    total = await page.locator("#total").text_content()
    
    # This assertion will fail
    assert total == "$0.00", f"Expected $0.00, got {total}"


# Example 3: Test with timeout
async def test_timeout_auto(page):
    """
    Test that times out waiting for an element.
    """
    await page.goto("https://example.com")
    
    # This will timeout and be reported
    await page.wait_for_selector("#nonexistent-element", timeout=3000)


# Example 4: Test without page fixture
def test_no_page_auto():
    """
    Test without page fixture - error is still reported but without page details.
    
    The support request will have:
    - description: the error
    - meta: test name, timestamp
    - controlTarget: None (no page available)
    """
    # This will fail
    assert 1 + 1 == 3, "Math is broken"


# Example 5: Test that passes (no report sent)
async def test_passing_auto(page):
    """
    Test that passes - no error report is sent.
    """
    await page.goto("https://example.com")
    title = await page.title()
    assert title  # Just check title exists

