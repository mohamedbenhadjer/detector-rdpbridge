"""
Error reporter with decorator and context manager support.

This module provides:
- Context manager for explicit page wrapping
- Decorator for auto-detecting page from test function
- Page info collectors (sync/async Playwright APIs)
- CDP targetId extraction (Chromium only)
- Screenshot capture (optional)
"""

import asyncio
import base64
import functools
import inspect
import logging
import traceback
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

from pw_ws_reporter.ws_client import (
    Config,
    ControlTarget,
    SupportRequestPayload,
    WsClient,
    create_meta,
)

logger = logging.getLogger("pw_ws_reporter")


# ============================================================================
# Page Info Collectors
# ============================================================================

async def collect_page_info(page: Any, config: Optional[Config] = None) -> dict:
    """
    Collect page information for the control target.
    
    Works with both sync and async Playwright Page APIs.
    
    Args:
        page: Playwright Page object (sync or async).
        config: Optional config for settings.
    
    Returns:
        Dictionary with url, title, targetId (if available), and screenshot.
    """
    if config is None:
        config = Config()
    
    info = {
        "url": None,
        "title": None,
        "targetId": None,
        "screenshot_b64": None,
    }
    
    try:
        # Get URL (property, works for both sync/async)
        if hasattr(page, "url"):
            info["url"] = page.url
        
        # Get title (method, might be async)
        if hasattr(page, "title"):
            title_result = page.title()
            if inspect.iscoroutine(title_result):
                info["title"] = await title_result
            else:
                info["title"] = title_result
        
        # Try to get CDP targetId (Chromium only)
        info["targetId"] = await _get_cdp_target_id(page)
        
        # Capture screenshot if enabled
        if config.PW_WS_CAPTURE_SCREENSHOT:
            info["screenshot_b64"] = await _capture_screenshot(page)
    
    except Exception as e:
        logger.debug(f"Error collecting page info: {e}")
    
    return info


async def _get_cdp_target_id(page: Any) -> Optional[str]:
    """
    Extract CDP targetId for Chromium-based browsers.
    
    This only works for Chromium (Chrome, Edge, Brave).
    
    Args:
        page: Playwright Page object.
    
    Returns:
        Target ID string or None if not available.
    """
    try:
        # Check if this is a Chromium browser
        browser_type = page.context.browser.browser_type.name
        if browser_type != "chromium":
            logger.debug(f"CDP targetId not available for {browser_type}")
            return None
        
        # Create CDP session
        cdp = await page.context.new_cdp_session(page)
        
        # Get target info
        result = await cdp.send("Target.getTargetInfo")
        target_id = result.get("targetInfo", {}).get("targetId")
        
        logger.debug(f"Extracted CDP targetId: {target_id}")
        return target_id
    
    except Exception as e:
        logger.debug(f"Failed to get CDP targetId: {e}")
        return None


async def _capture_screenshot(page: Any) -> Optional[str]:
    """
    Capture a screenshot and return it as base64.
    
    Args:
        page: Playwright Page object.
    
    Returns:
        Base64-encoded screenshot or None on failure.
    """
    try:
        screenshot_result = page.screenshot()
        
        # Handle both sync and async
        if inspect.iscoroutine(screenshot_result):
            screenshot_bytes = await screenshot_result
        else:
            screenshot_bytes = screenshot_result
        
        b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        logger.debug(f"Captured screenshot ({len(b64)} chars)")
        return b64
    
    except Exception as e:
        logger.debug(f"Failed to capture screenshot: {e}")
        return None


# ============================================================================
# Error Reporting
# ============================================================================

async def report_error(
    exc: Exception,
    page: Any = None,
    description_hint: Optional[str] = None,
    test_name: str = "unknown_test",
    config: Optional[Config] = None,
) -> None:
    """
    Report an error to the Flutter app via WebSocket.
    
    This function:
    1. Collects page info (if page is provided)
    2. Builds a support request payload
    3. Sends it to the Flutter app
    4. Logs the outcome
    
    Never raises exceptions (to avoid crashing tests).
    
    Args:
        exc: The exception that occurred.
        page: Playwright Page object (optional).
        description_hint: Optional hint to prepend to description.
        test_name: Name/ID of the test.
        config: Optional config object.
    """
    if config is None:
        config = Config()
    
    try:
        # Build description
        exc_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        if description_hint:
            description = f"{description_hint}\n\n{exc_str}"
        else:
            description = f"Playwright failure: {exc}\n\n{exc_str}"
        
        # Collect page info if available
        control_target = None
        screenshot_b64 = None
        
        if page is not None:
            page_info = await collect_page_info(page, config)
            
            control_target = ControlTarget(
                browser=config.BROWSER,
                debugPort=config.DEBUG_PORT,
                urlContains=page_info["url"],
                titleContains=page_info["title"],
                targetId=page_info["targetId"],
            )
            
            screenshot_b64 = page_info["screenshot_b64"]
        
        # Build payload
        meta = create_meta(
            test_name=test_name,
            screenshot_b64=screenshot_b64,
            trace_path=config.PW_WS_TRACE_PATH,
        )
        
        payload = SupportRequestPayload(
            description=description,
            controlTarget=control_target,
            meta=meta,
        )
        
        # Send to Flutter app
        client = WsClient(config)
        try:
            result = await client.send_support_request(payload)
            logger.info(
                f"Support request sent successfully: "
                f"roomId={result['roomId']}, requestId={result['requestId']}"
            )
        finally:
            await client.aclose()
    
    except Exception as e:
        logger.error(f"Failed to report error to Flutter app: {e}", exc_info=True)


# ============================================================================
# Context Manager
# ============================================================================

@asynccontextmanager
async def _reporter_context(
    page: Any = None,
    description_hint: Optional[str] = None,
    test_name: str = "unknown_test",
):
    """
    Async context manager that reports errors on exception.
    
    Args:
        page: Playwright Page object (optional).
        description_hint: Optional hint for error description.
        test_name: Name/ID of the test.
    """
    try:
        yield
    except Exception as exc:
        # Report the error (but don't crash)
        await report_error(
            exc=exc,
            page=page,
            description_hint=description_hint,
            test_name=test_name,
        )
        # Re-raise so the test fails normally
        raise


# ============================================================================
# Public API: Decorator and Context Manager
# ============================================================================

def report_errors_to_flutter(
    page: Any = None,
    description_hint: Optional[str] = None,
):
    """
    Decorator or context manager for reporting Playwright errors to Flutter.
    
    Usage as context manager (explicit page):
        async with report_errors_to_flutter(page, description_hint="Login failed"):
            await page.goto("https://example.com")
            ...
    
    Usage as decorator (auto-detect page):
        @report_errors_to_flutter(description_hint="Checkout failed")
        async def test_checkout(page):
            await page.goto("https://example.com/checkout")
            ...
    
    Args:
        page: Playwright Page object. If None, acts as decorator.
        description_hint: Optional hint to include in error description.
    
    Returns:
        Context manager if page provided, decorator otherwise.
    """
    # If page is provided, return context manager
    if page is not None:
        return _reporter_context(
            page=page,
            description_hint=description_hint,
            test_name="context_manager_test",
        )
    
    # Otherwise, return decorator that auto-detects page
    def decorator(func: Callable) -> Callable:
        """Decorator that wraps async test functions."""
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Try to find page argument
            page_arg = _find_page_arg(func, args, kwargs)
            
            # Get test name from function
            test_name = f"{func.__module__}.{func.__qualname__}"
            
            # Wrap execution with error reporting
            async with _reporter_context(
                page=page_arg,
                description_hint=description_hint,
                test_name=test_name,
            ):
                return await func(*args, **kwargs)
        
        # Also support sync functions (convert to async)
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            page_arg = _find_page_arg(func, args, kwargs)
            test_name = f"{func.__module__}.{func.__qualname__}"
            
            async def async_exec():
                async with _reporter_context(
                    page=page_arg,
                    description_hint=description_hint,
                    test_name=test_name,
                ):
                    return func(*args, **kwargs)
            
            return asyncio.run(async_exec())
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def _find_page_arg(func: Callable, args: tuple, kwargs: dict) -> Any:
    """
    Find the 'page' argument from function signature.
    
    Looks for:
    1. Keyword argument named 'page'
    2. Positional argument in position matching 'page' parameter
    
    Args:
        func: Function to inspect.
        args: Positional arguments.
        kwargs: Keyword arguments.
    
    Returns:
        Page object or None if not found.
    """
    # Check kwargs first
    if "page" in kwargs:
        return kwargs["page"]
    
    # Check positional args by matching signature
    try:
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        
        if "page" in param_names:
            page_idx = param_names.index("page")
            if page_idx < len(args):
                return args[page_idx]
    except Exception as e:
        logger.debug(f"Failed to find page argument: {e}")
    
    return None

