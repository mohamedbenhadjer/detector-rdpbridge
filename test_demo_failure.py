"""
Demo test file with intentional failures to test pw-ws-reporter.

This file contains Playwright tests that will fail on purpose,
allowing you to verify that the reporter sends WebSocket notifications.
"""

import pytest


async def test_missing_element_failure(page):
    """
    Test that fails because an element doesn't exist.
    
    This will trigger a timeout error and send a support request
    to your Flutter app with the page URL and title.
    """
    await page.goto("https://example.com")
    
    # This will fail - element doesn't exist
    await page.wait_for_selector("#nonexistent-button", timeout=3000)


async def test_assertion_failure(page):
    """
    Test that fails on an assertion.
    
    This will send a support request with the assertion error details.
    """
    await page.goto("https://example.com")
    
    title = await page.title()
    
    # This assertion will fail
    assert title == "Wrong Title", f"Expected 'Wrong Title', got '{title}'"


async def test_click_failure(page):
    """
    Test that fails when trying to click a non-existent element.
    """
    await page.goto("https://playwright.dev")
    
    # This will fail - element doesn't exist
    await page.click("#does-not-exist", timeout=3000)


async def test_navigation_failure(page):
    """
    Test that fails on navigation timeout.
    """
    # This will timeout trying to reach an invalid URL
    await page.goto("https://this-domain-does-not-exist-12345.com", timeout=5000)

