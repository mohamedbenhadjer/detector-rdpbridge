"""
Pytest plugin for automatic error reporting.

This plugin:
- Auto-loads via pytest11 entry point
- Hooks into test failures
- Sends WebSocket notification for each failure
- Uses background async worker to avoid event loop conflicts
"""

import asyncio
import logging
import threading
from typing import Any, Optional

import pytest

from pw_ws_reporter.reporter import report_error

logger = logging.getLogger("pw_ws_reporter")


# ============================================================================
# Background Async Worker
# ============================================================================

class BackgroundAsyncWorker:
    """
    Background worker that runs async tasks in a dedicated thread.
    
    This is necessary because:
    1. Tests might have their own event loops
    2. We need to run async network I/O without interfering
    3. Pytest hooks are synchronous
    """
    
    def __init__(self):
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._started = False
        self._lock = threading.Lock()
    
    def start(self):
        """Start the background worker thread."""
        with self._lock:
            if self._started:
                return
            
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            self._started = True
            logger.debug("Background async worker started")
    
    def _run_loop(self):
        """Run the event loop in the background thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def run_async(self, coro):
        """
        Schedule a coroutine to run in the background loop.
        
        Args:
            coro: Coroutine to execute.
        """
        if not self._started:
            self.start()
        
        if self.loop is None:
            logger.error("Background loop not available")
            return
        
        # Schedule the coroutine in the background loop
        asyncio.run_coroutine_threadsafe(coro, self.loop)
    
    def stop(self):
        """Stop the background worker (cleanup)."""
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
            logger.debug("Background async worker stopped")


# Global worker instance
_worker = BackgroundAsyncWorker()


# ============================================================================
# Pytest Hooks
# ============================================================================

def pytest_configure(config):
    """Called after command line options are parsed."""
    # Start the background worker
    _worker.start()
    logger.debug("pytest_playwright_ws_reporter plugin loaded")


def pytest_runtest_makereport(item, call):
    """
    Called to create a test report for each test phase.
    
    We hook into the 'call' phase (the actual test execution) to detect
    failures and send WebSocket notifications.
    
    Args:
        item: Test item.
        call: Information about the test call.
    """
    # Only process failures during the "call" phase (actual test execution)
    if call.when != "call":
        return
    
    if call.excinfo is None:
        return  # Test passed
    
    # Test failed - extract information
    exc = call.excinfo.value
    test_name = item.nodeid
    
    # Try to get the 'page' fixture if it was used
    page = None
    if hasattr(item, "funcargs") and "page" in item.funcargs:
        page = item.funcargs["page"]
    
    logger.info(f"Test failed: {test_name}")
    
    # Send error report in background
    _worker.run_async(
        report_error(
            exc=exc,
            page=page,
            test_name=test_name,
        )
    )


def pytest_sessionfinish(session, exitstatus):
    """
    Called after the test session finishes.
    
    We give the background worker a moment to finish pending tasks.
    
    Args:
        session: Pytest session.
        exitstatus: Exit status code.
    """
    # Give background tasks a moment to complete
    # (They're daemon threads, so they'll be killed on exit anyway)
    import time
    time.sleep(1)
    
    logger.debug("pytest session finished")

