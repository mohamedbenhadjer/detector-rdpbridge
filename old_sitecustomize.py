"""
Sitecustomize hook for Playwright error detection.
Auto-loaded by Python when this directory is in PYTHONPATH.
Intercepts Playwright exceptions and sends support requests without modifying user code.
"""
import os
import sys
import logging
from pathlib import Path
from typing import Optional, Any, Dict

# Only activate if explicitly enabled
if os.environ.get("MINIAGENT_ENABLED", "1") != "1":
    sys.exit(0)

logger = logging.getLogger("miniagent.hook")
logger.setLevel(logging.INFO)

# Track if we've already patched
_patched = False


def _get_page_info(page_obj) -> Dict[str, Any]:
    """Extract URL, title, and page ID from a Playwright Page object."""
    info = {"url": None, "title": None, "page_id": None}
    
    try:
        if hasattr(page_obj, "url"):
            info["url"] = page_obj.url
        if hasattr(page_obj, "title"):
            try:
                info["title"] = page_obj.title()
            except:
                pass
        # Use object id as page identifier
        info["page_id"] = str(id(page_obj))
    except:
        pass
    
    return info


def _intercept_playwright():
    """Monkey-patch Playwright to intercept errors and inject debug flags."""
    global _patched
    
    if _patched:
        return
    
    try:
        # Import Playwright components
        from playwright.sync_api import BrowserType as SyncBrowserType, Page as SyncPage
        from playwright.async_api import BrowserType as AsyncBrowserType, Page as AsyncPage
        from playwright._impl._errors import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
    except ImportError:
        logger.debug("Playwright not installed, skipping hook")
        return
    
    # Get support manager
    try:
        from miniagent_ws import get_support_manager
        manager = get_support_manager()
        if not manager:
            logger.warning("Support manager not available")
            return
    except ImportError as e:
        logger.error(f"Failed to import miniagent_ws: {e}")
        return
    
    # Track browser info per launch
    _browser_info: Dict[int, Dict[str, Any]] = {}
    
    # === Chromium debug port injection ===
    
    def _inject_debug_args(args: list, browser_name: str) -> list:
        """Inject remote debugging flags for Chromium-based browsers."""
        if browser_name not in ("chromium", "chrome", "msedge"):
            return args
        
        args = list(args) if args else []
        
        # Check if debug port already set
        has_debug = any("--remote-debugging-port" in str(arg) for arg in args)
        if not has_debug:
            args.extend([
                "--remote-debugging-address=127.0.0.1",
                "--remote-debugging-port=0"  # Let Chrome pick a free port
            ])
            logger.debug("Injected remote debugging flags")
        
        return args
    
    def _read_devtools_port(user_data_dir: Optional[Path]) -> Optional[int]:
        """Read the DevToolsActivePort file to get the actual debug port."""
        if not user_data_dir:
            return None
        
        try:
            port_file = Path(user_data_dir) / "DevToolsActivePort"
            if port_file.exists():
                lines = port_file.read_text().strip().split('\n')
                if lines:
                    port = int(lines[0])
                    logger.info(f"Detected debug port: {port}")
                    return port
        except Exception as e:
            logger.debug(f"Failed to read DevToolsActivePort: {e}")
        
        return None
    
    # Patch sync BrowserType.launch
    _orig_sync_launch = SyncBrowserType.launch
    
    def _patched_sync_launch(self, *args, **kwargs):
        browser_name = self.name
        
        # Inject debug args for Chromium
        if "args" in kwargs:
            kwargs["args"] = _inject_debug_args(kwargs["args"], browser_name)
        elif browser_name in ("chromium", "chrome", "msedge"):
            kwargs["args"] = _inject_debug_args([], browser_name)
        
        browser = _orig_sync_launch(self, *args, **kwargs)
        
        # Try to read debug port
        debug_port = None
        if browser_name in ("chromium", "chrome", "msedge"):
            # Access internal context if available
            try:
                if hasattr(browser, "_impl") and hasattr(browser._impl, "_browser_type"):
                    # Try to get user data dir from persistent context
                    pass
                # For now, store browser type
                _browser_info[id(browser)] = {
                    "browser": browser_name,
                    "debug_port": debug_port
                }
            except:
                pass
        else:
            _browser_info[id(browser)] = {
                "browser": "firefox" if browser_name == "firefox" else "webkit",
                "debug_port": None
            }
        
        return browser
    
    SyncBrowserType.launch = _patched_sync_launch
    
    # Patch sync BrowserType.launch_persistent_context
    _orig_sync_launch_persistent = SyncBrowserType.launch_persistent_context
    
    def _patched_sync_launch_persistent(self, user_data_dir, *args, **kwargs):
        browser_name = self.name
        
        # Inject debug args for Chromium
        if "args" in kwargs:
            kwargs["args"] = _inject_debug_args(kwargs["args"], browser_name)
        elif browser_name in ("chromium", "chrome", "msedge"):
            kwargs["args"] = _inject_debug_args([], browser_name)
        
        context = _orig_sync_launch_persistent(self, user_data_dir, *args, **kwargs)
        
        # Read debug port for Chromium
        debug_port = None
        if browser_name in ("chromium", "chrome", "msedge"):
            import time
            time.sleep(0.5)  # Give Chrome time to write the file
            debug_port = _read_devtools_port(Path(user_data_dir))
        
        _browser_info[id(context)] = {
            "browser": browser_name if browser_name in ("chromium", "firefox", "webkit") else "chromium",
            "debug_port": debug_port
        }
        
        return context
    
    SyncBrowserType.launch_persistent_context = _patched_sync_launch_persistent
    
    # === Error interception ===
    
    def _wrap_method(cls, method_name: str, is_async: bool = False):
        """Wrap a method to catch and report Playwright exceptions."""
        orig_method = getattr(cls, method_name)
        
        def _sync_wrapper(self, *args, **kwargs):
            try:
                return orig_method(self, *args, **kwargs)
            except (PlaywrightTimeoutError, PlaywrightError, AssertionError) as e:
                # Extract page info if this is a Page method
                page_info = _get_page_info(self) if isinstance(self, (SyncPage, AsyncPage)) else {}
                
                # Get browser info
                browser_info = {"browser": "chromium", "debug_port": None}
                try:
                    # Try to find browser from page
                    if hasattr(self, "context") and hasattr(self.context, "browser"):
                        browser_obj = self.context.browser
                        if browser_obj and id(browser_obj) in _browser_info:
                            browser_info = _browser_info[id(browser_obj)]
                    elif hasattr(self, "_impl") and hasattr(self._impl, "_browser_type"):
                        # Fallback: detect from browser type
                        bt_name = self._impl._browser_type.name
                        browser_info["browser"] = bt_name if bt_name in ("firefox", "webkit") else "chromium"
                except:
                    pass
                
                # Determine error type
                error_type = type(e).__name__
                error_msg = str(e)[:200]
                
                # Trigger support request
                manager.trigger_support_request(
                    reason=error_type,
                    details=f"{method_name}: {error_msg}",
                    browser=browser_info["browser"],
                    debug_port=browser_info.get("debug_port"),
                    url=page_info.get("url"),
                    title=page_info.get("title"),
                    page_id=page_info.get("page_id")
                )
                
                # Re-raise the exception
                raise
        
        async def _async_wrapper(self, *args, **kwargs):
            try:
                return await orig_method(self, *args, **kwargs)
            except (PlaywrightTimeoutError, PlaywrightError, AssertionError) as e:
                page_info = _get_page_info(self) if isinstance(self, (SyncPage, AsyncPage)) else {}
                
                browser_info = {"browser": "chromium", "debug_port": None}
                try:
                    if hasattr(self, "context") and hasattr(self.context, "browser"):
                        browser_obj = self.context.browser
                        if browser_obj and id(browser_obj) in _browser_info:
                            browser_info = _browser_info[id(browser_obj)]
                except:
                    pass
                
                error_type = type(e).__name__
                error_msg = str(e)[:200]
                
                manager.trigger_support_request(
                    reason=error_type,
                    details=f"{method_name}: {error_msg}",
                    browser=browser_info["browser"],
                    debug_port=browser_info.get("debug_port"),
                    url=page_info.get("url"),
                    title=page_info.get("title"),
                    page_id=page_info.get("page_id")
                )
                
                raise
        
        wrapper = _async_wrapper if is_async else _sync_wrapper
        wrapper.__name__ = method_name
        wrapper.__doc__ = orig_method.__doc__
        
        setattr(cls, method_name, wrapper)
    
    # Wrap common Page methods (sync)
    page_methods = ["goto", "click", "fill", "press", "type", "select_option", "check", 
                    "uncheck", "wait_for_selector", "wait_for_load_state", "wait_for_url",
                    "wait_for_timeout", "screenshot", "pdf"]
    
    for method in page_methods:
        if hasattr(SyncPage, method):
            _wrap_method(SyncPage, method, is_async=False)
    
    # Wrap common Page methods (async)
    for method in page_methods:
        if hasattr(AsyncPage, method):
            _wrap_method(AsyncPage, method, is_async=True)
    
    # Wrap Locator methods (sync)
    try:
        from playwright.sync_api import Locator as SyncLocator
        from playwright.async_api import Locator as AsyncLocator
        
        locator_methods = ["click", "fill", "press", "type", "select_option", "check",
                          "uncheck", "wait_for", "screenshot"]
        
        for method in locator_methods:
            if hasattr(SyncLocator, method):
                _wrap_method(SyncLocator, method, is_async=False)
        
        for method in locator_methods:
            if hasattr(AsyncLocator, method):
                _wrap_method(AsyncLocator, method, is_async=True)
    except ImportError:
        pass
    
    # Wrap expect assertions
    try:
        from playwright.sync_api import expect as sync_expect
        # Note: expect uses a different pattern, would need more complex wrapping
        # For now, assertion errors will be caught by the page method wrappers
    except ImportError:
        pass
    
    _patched = True
    logger.info("Playwright interception activated")


# Activate interception on module import
try:
    _intercept_playwright()
except Exception as e:
    logger.error(f"Failed to intercept Playwright: {e}", exc_info=True)


