"""
Playwright WebSocket Reporter
==============================

A Python module that detects errors in Playwright tests and notifies
a local Flutter desktop app via WebSocket.

Usage:
    # As a decorator
    @report_errors_to_flutter(description_hint="Login flow failed")
    async def test_login(page):
        await page.goto("https://example.com")
        ...

    # As a context manager
    async with report_errors_to_flutter(page, description_hint="Checkout failed"):
        await page.goto("https://example.com/checkout")
        ...

    # Automatically via pytest plugin (auto-loaded)
    # Just run: pytest tests/

    # CLI
    pw-ws-reporter run pytest tests/test_login.py
    pw-ws-reporter send --desc "Test error" --url "https://example.com"
"""

__version__ = "1.0.0"

from pw_ws_reporter.reporter import report_errors_to_flutter

__all__ = ["report_errors_to_flutter", "__version__"]

