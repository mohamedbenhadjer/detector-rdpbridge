"""
Sitecustomize hook for Playwright error detection.
Auto-loaded by Python when this directory is in PYTHONPATH.
Intercepts Playwright exceptions and sends support requests without modifying user code.
"""
import os
import sys
import logging
import time
import asyncio
import threading
import json
from pathlib import Path
from typing import Optional, Any, Dict
from http.server import HTTPServer, BaseHTTPRequestHandler

# Only activate if explicitly enabled
if os.environ.get("MINIAGENT_ENABLED", "1") != "1":
    sys.exit(0)

logger = logging.getLogger("miniagent.hook")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(handler)

# Track if we've already patched
_patched = False

# Error handling mode configuration
_MODE = os.environ.get("MINIAGENT_ON_ERROR", "report").lower()  # report|hold|swallow
_HOLD_RAW = os.environ.get("MINIAGENT_HOLD_SECS", "").strip().lower()
_RESUME_FILE = os.environ.get("MINIAGENT_RESUME_FILE", "/tmp/miniagent_resume")

# Optional HTTP resume endpoint configuration
_RESUME_HTTP_ENABLED = os.environ.get("MINIAGENT_RESUME_HTTP", "0") == "1"
_RESUME_HTTP_HOST = os.environ.get("MINIAGENT_RESUME_HTTP_HOST", "127.0.0.1")
_RESUME_HTTP_PORT = int(os.environ.get("MINIAGENT_RESUME_HTTP_PORT", "8787"))
_RESUME_HTTP_TOKEN = os.environ.get("MINIAGENT_RESUME_HTTP_TOKEN", "").strip()

# Remote debugging port configuration
_DEBUG_PORT = int(os.environ.get("MINIAGENT_DEBUG_PORT", "9222"))
_FORCE_DEBUG_PORT = os.environ.get("MINIAGENT_FORCE_DEBUG_PORT", "1") == "1"


def _hold_deadline():
    """Compute hold deadline from MINIAGENT_HOLD_SECS env var."""
    if _HOLD_RAW in ("", "forever", "inf"):
        return None
    try:
        return time.time() + float(_HOLD_RAW)
    except Exception:
        return None


def _park_until_resume(reason: str, details: str):
    """
    Block the process until resume signal or timeout.
    Resume happens when MINIAGENT_RESUME_FILE is created or deadline is reached.
    """
    logger.warning(f"Holding on error ({reason}) - waiting for agent. Resume file: {_RESUME_FILE}")
    deadline = _hold_deadline()
    
    while True:
        try:
            if _RESUME_FILE and Path(_RESUME_FILE).exists():
                logger.info("Resume signal detected; continuing.")
                try:
                    Path(_RESUME_FILE).unlink(missing_ok=True)
                except Exception:
                    pass
                return
        except Exception:
            pass
        
        if deadline and time.time() >= deadline:
            logger.info("Hold timeout reached; continuing.")
            return
        
        time.sleep(1.0)


class _ResumeRequestHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for POST /resume with bearer auth.
    Creates the resume file watched by the hold loop.
    """

    server_version = "MiniAgentResumeHTTP/1.0"
    sys_version = ""

    def log_message(self, format, *args):
        try:
            logger.info("resume-http: " + (format % args))
        except Exception:
            pass

    def _send_json(self, status: int, payload: Dict[str, Any]):
        try:
            body = json.dumps(payload).encode("utf-8")
        except Exception:
            body = b"{}"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def do_POST(self):  # noqa: N802 (method name by BaseHTTPRequestHandler)
        if self.path != "/resume":
            self._send_json(404, {"ok": False, "error": "not_found"})
            return

        token = _RESUME_HTTP_TOKEN
        auth_header = self.headers.get("Authorization", "")

        if not token or not auth_header.startswith("Bearer "):
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return

        expected = f"Bearer {token}"
        if auth_header.strip() != expected:
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return

        try:
            Path(_RESUME_FILE).touch(exist_ok=True)
            logger.info("Resume HTTP: resume signal emitted via file")
            self._send_json(200, {"ok": True})
        except Exception as e:
            logger.error(f"Resume HTTP: failed to emit resume signal: {e}")
            self._send_json(500, {"ok": False, "error": "server_error"})


def _start_resume_http_server():
    """Start a daemonized HTTP server that exposes POST /resume.
    Only starts when MINIAGENT_RESUME_HTTP=1 and a token is configured.
    """
    if not _RESUME_HTTP_ENABLED:
        return

    if not _RESUME_HTTP_TOKEN:
        logger.error("Resume HTTP enabled but MINIAGENT_RESUME_HTTP_TOKEN is not set; not starting HTTP server")
        return

    try:
        httpd = HTTPServer((_RESUME_HTTP_HOST, _RESUME_HTTP_PORT), _ResumeRequestHandler)
    except Exception as e:
        logger.warning(f"Resume HTTP: failed to bind {_RESUME_HTTP_HOST}:{_RESUME_HTTP_PORT}: {e}")
        return

    th = threading.Thread(target=httpd.serve_forever, name="miniagent-resume-http", daemon=True)
    th.start()
    logger.info(f"Resume HTTP server listening on http://{_RESUME_HTTP_HOST}:{_RESUME_HTTP_PORT}")


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
        
        # Remove existing debug port args if forcing
        if _FORCE_DEBUG_PORT:
            args = [arg for arg in args if "--remote-debugging-port" not in str(arg)]
            args = [arg for arg in args if "--remote-debugging-address" not in str(arg)]
        
        # Check if debug port already set (after potential removal)
        has_debug = any("--remote-debugging-port" in str(arg) for arg in args)
        if not has_debug:
            args.extend([
                "--remote-debugging-address=127.0.0.1",
                f"--remote-debugging-port={_DEBUG_PORT}"
            ])
            logger.debug(f"Injected remote debugging flags (port {_DEBUG_PORT})")
        
        # Add flags to keep background/occluded tabs rendering
        args.extend([
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling",
        ])
        
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
        
        # Set debug port for Chromium (we know it because we set it)
        debug_port = None
        if browser_name in ("chromium", "chrome", "msedge"):
            debug_port = _DEBUG_PORT
            _browser_info[id(browser)] = {
                "browser": browser_name,
                "debug_port": debug_port
            }
            logger.info(f"Chromium launched with debug port {debug_port}")
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
        
        # Set debug port for Chromium (we know it because we set it)
        debug_port = None
        if browser_name in ("chromium", "chrome", "msedge"):
            debug_port = _DEBUG_PORT
            
            # Sanity check: read DevToolsActivePort file if available
            import time
            time.sleep(0.5)  # Give Chrome time to write the file
            detected_port = _read_devtools_port(Path(user_data_dir))
            if detected_port and detected_port != debug_port:
                logger.warning(f"DevToolsActivePort mismatch: configured={debug_port}, detected={detected_port}")
            
            logger.info(f"Chromium persistent context launched with debug port {debug_port}")
        
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
        
        def _resolve_page_obj(obj):
            """Resolve Page object from Page or Locator instances."""
            try:
                # If it's already a Page (sync or async), we're done
                if isinstance(obj, (SyncPage, AsyncPage)):
                    return obj
                # Common Locator links
                if hasattr(obj, "page"):
                    return obj.page
                if hasattr(obj, "_page"):
                    return obj._page
                # Fallback via frame → page
                if hasattr(obj, "_frame") and hasattr(obj._frame, "page"):
                    return obj._frame.page
            except Exception:
                pass
            return None
        
        def _sync_wrapper(self, *args, **kwargs):
            try:
                return orig_method(self, *args, **kwargs)
            except (PlaywrightTimeoutError, PlaywrightError, AssertionError) as e:
                # Resolve page object from Page or Locator
                page_obj = _resolve_page_obj(self)
                page_info = _get_page_info(page_obj) if page_obj else {}
                
                # Get browser info from resolved page
                browser_info = {"browser": "chromium", "debug_port": None}
                try:
                    if page_obj and hasattr(page_obj, "context"):
                        ctx = page_obj.context
                        # Try via Browser → mapping
                        if hasattr(ctx, "browser") and ctx.browser and id(ctx.browser) in _browser_info:
                            browser_info = _browser_info[id(ctx.browser)]
                        # Persistent context path stores mapping by context id
                        elif id(ctx) in _browser_info:
                            browser_info = _browser_info[id(ctx)]
                    # Fallback: detect browser type off the object if needed
                    elif hasattr(self, "_impl") and hasattr(self._impl, "_browser_type"):
                        bt_name = self._impl._browser_type.name
                        browser_info["browser"] = bt_name if bt_name in ("firefox", "webkit") else "chromium"
                except Exception:
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
                
                # Handle based on mode
                if _MODE == "hold":
                    _park_until_resume(error_type, error_msg)
                    return None
                if _MODE == "swallow":
                    return None
                # Default: re-raise the exception
                raise
        
        async def _async_wrapper(self, *args, **kwargs):
            try:
                return await orig_method(self, *args, **kwargs)
            except (PlaywrightTimeoutError, PlaywrightError, AssertionError) as e:
                # Resolve page object from Page or Locator
                page_obj = _resolve_page_obj(self)
                page_info = _get_page_info(page_obj) if page_obj else {}
                
                # Get browser info from resolved page
                browser_info = {"browser": "chromium", "debug_port": None}
                try:
                    if page_obj and hasattr(page_obj, "context"):
                        ctx = page_obj.context
                        # Try via Browser → mapping
                        if hasattr(ctx, "browser") and ctx.browser and id(ctx.browser) in _browser_info:
                            browser_info = _browser_info[id(ctx.browser)]
                        # Persistent context path stores mapping by context id
                        elif id(ctx) in _browser_info:
                            browser_info = _browser_info[id(ctx)]
                    # Fallback: detect browser type off the object if needed
                    elif hasattr(self, "_impl") and hasattr(self._impl, "_browser_type"):
                        bt_name = self._impl._browser_type.name
                        browser_info["browser"] = bt_name if bt_name in ("firefox", "webkit") else "chromium"
                except Exception:
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
                
                # Handle based on mode
                if _MODE == "hold":
                    # Async park until resume/timeout
                    logger.warning(f"Holding on error ({error_type}) - waiting for agent. Resume file: {_RESUME_FILE}")
                    deadline = _hold_deadline()
                    while True:
                        try:
                            if _RESUME_FILE and Path(_RESUME_FILE).exists():
                                logger.info("Resume signal detected; continuing.")
                                try:
                                    Path(_RESUME_FILE).unlink(missing_ok=True)
                                except Exception:
                                    pass
                                return None
                        except Exception:
                            pass
                        if deadline and time.time() >= deadline:
                            logger.info("Hold timeout reached; continuing.")
                            return None
                        await asyncio.sleep(1.0)
                
                if _MODE == "swallow":
                    return None
                # Default: re-raise the exception
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

# Start HTTP resume server (if enabled)
try:
    _start_resume_http_server()
except Exception as e:
    logger.error(f"Failed to start resume HTTP server: {e}")
