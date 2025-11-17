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
import socket
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

# Popup/tab prevention configuration
_PREVENT_NEW_TABS = os.environ.get("MINIAGENT_PREVENT_NEW_TABS", "1") == "1"
_ALLOW_NEW_TAB_REGEX = os.environ.get("MINIAGENT_ALLOW_NEW_TAB_REGEX", "").strip()
_PREVENT_TABS_LOG = os.environ.get("MINIAGENT_PREVENT_TABS_LOG", "0") == "1"

# Parse allowlist regex patterns
_ALLOW_NEW_TAB_PATTERNS = []
if _ALLOW_NEW_TAB_REGEX:
    import re
    try:
        _ALLOW_NEW_TAB_PATTERNS = [
            re.compile(pattern.strip()) 
            for pattern in _ALLOW_NEW_TAB_REGEX.split(",") 
            if pattern.strip()
        ]
    except Exception as e:
        logger.warning(f"Failed to parse MINIAGENT_ALLOW_NEW_TAB_REGEX: {e}")

# JavaScript snippet to prevent new tabs/popups
_POPUP_PREVENTION_SCRIPT = """
// Override window.open to reuse same tab
(function() {
    const originalOpen = window.open;
    window.open = function(url, target, features) {
        if (!url || url === 'about:blank' || url === '') {
            return null;
        }
        // Navigate in the same tab
        setTimeout(() => {
            window.location.href = url;
        }, 0);
        return window;
    };
})();

// Intercept clicks on links with target="_blank"
document.addEventListener('click', (event) => {
    const link = event.target && event.target.closest && event.target.closest('a[target="_blank"]');
    if (!link) return;
    event.preventDefault();
    event.stopPropagation();
    window.location.href = link.href;
}, true);
"""


def _find_free_debug_port(base_port: int, max_attempts: int = 50) -> int:
    """
    Find a free port starting from base_port by probing base_port, base_port+1, etc.
    Returns the first free port found, or base_port if none found (with warning).
    """
    for offset in range(max_attempts):
        port = base_port + offset
        try:
            # Try to bind to the port to check if it's free
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                logger.debug(f"Found free debug port: {port}")
                return port
        except OSError:
            # Port is in use, try next one
            continue
    
    # If we exhausted all attempts, warn and fall back to base_port
    logger.warning(f"Could not find free port in range {base_port}-{base_port + max_attempts - 1}, falling back to {base_port}")
    return base_port


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


def _is_url_allowed_for_new_tab(url: Optional[str]) -> bool:
    """Check if URL matches allowlist patterns for new tab creation."""
    if not url or not _ALLOW_NEW_TAB_PATTERNS:
        return False
    
    for pattern in _ALLOW_NEW_TAB_PATTERNS:
        try:
            if pattern.search(url):
                return True
        except Exception:
            pass
    
    return False


def _install_popup_prevention_on_page(page_obj):
    """Install popup prevention on a Playwright Page object (sync or async).
    
    Adds init script to override window.open and intercept target="_blank" clicks.
    Also adds popup handler to immediately close any popups that still appear.
    """
    if not _PREVENT_NEW_TABS:
        return
    
    import inspect
    is_async = inspect.iscoroutinefunction(getattr(page_obj.__class__, 'add_init_script', None))
    
    try:
        # Add init script to override window.open and intercept _blank links
        if hasattr(page_obj, 'add_init_script'):
            result = page_obj.add_init_script(_POPUP_PREVENTION_SCRIPT)
            # If async, we can't await here, but the script will still be added
            if _PREVENT_TABS_LOG:
                logger.info(f"Popup prevention script installed on page {id(page_obj)}")
        
        # Add popup handler to close any popups that still manage to open
        if hasattr(page_obj, 'on'):
            def _popup_handler(popup):
                try:
                    popup_url = None
                    try:
                        popup_url = popup.url
                    except:
                        pass
                    
                    # Check if popup URL is in allowlist
                    if popup_url and _is_url_allowed_for_new_tab(popup_url):
                        if _PREVENT_TABS_LOG:
                            logger.info(f"Allowing popup with URL: {popup_url}")
                        return
                    
                    # Close the popup - handle both sync and async
                    close_result = popup.close()
                    # If it's a coroutine, schedule it properly
                    if inspect.iscoroutine(close_result):
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                asyncio.create_task(close_result)
                            else:
                                loop.run_until_complete(close_result)
                        except:
                            # Fallback: let it be garbage collected
                            pass
                    
                    if _PREVENT_TABS_LOG:
                        logger.info(f"Closed popup with URL: {popup_url or 'unknown'}")
                except Exception as e:
                    if _PREVENT_TABS_LOG:
                        logger.warning(f"Failed to close popup: {e}")
            
            page_obj.on("popup", _popup_handler)
        
    except Exception as e:
        logger.warning(f"Failed to configure popup prevention on page: {e}")


def _install_popup_prevention_on_context(context_obj):
    """Install popup prevention on a BrowserContext (sync or async).
    
    Attaches a page handler that installs prevention on all new pages.
    """
    if not _PREVENT_NEW_TABS:
        return
    
    try:
        if hasattr(context_obj, 'on'):
            def _page_handler(page):
                _install_popup_prevention_on_page(page)
                if _PREVENT_TABS_LOG:
                    logger.info(f"Auto-installed popup prevention on new page {id(page)}")
            
            context_obj.on("page", _page_handler)
            if _PREVENT_TABS_LOG:
                logger.info(f"Popup prevention page handler installed on context {id(context_obj)}")
    except Exception as e:
        logger.warning(f"Failed to configure popup prevention on context: {e}")


async def _install_popup_prevention_on_page_async(page_obj):
    """Async version - Install popup prevention on an async Playwright Page object.
    
    Adds init script to override window.open and intercept target="_blank" clicks.
    Also adds popup handler to immediately close any popups that still appear.
    """
    if not _PREVENT_NEW_TABS:
        return
    
    try:
        # Add init script to override window.open and intercept _blank links
        if hasattr(page_obj, 'add_init_script'):
            await page_obj.add_init_script(_POPUP_PREVENTION_SCRIPT)
            if _PREVENT_TABS_LOG:
                logger.info(f"Popup prevention script installed on async page {id(page_obj)}")
        
        # Add popup handler to close any popups that still manage to open
        if hasattr(page_obj, 'on'):
            async def _popup_handler(popup):
                try:
                    popup_url = None
                    try:
                        popup_url = popup.url
                    except:
                        pass
                    
                    # Check if popup URL is in allowlist
                    if popup_url and _is_url_allowed_for_new_tab(popup_url):
                        if _PREVENT_TABS_LOG:
                            logger.info(f"Allowing popup with URL: {popup_url}")
                        return
                    
                    # Close the popup
                    await popup.close()
                    if _PREVENT_TABS_LOG:
                        logger.info(f"Closed async popup with URL: {popup_url or 'unknown'}")
                except Exception as e:
                    if _PREVENT_TABS_LOG:
                        logger.warning(f"Failed to close async popup: {e}")
            
            page_obj.on("popup", _popup_handler)
        
    except Exception as e:
        logger.warning(f"Failed to configure popup prevention on async page: {e}")


def _install_popup_prevention_on_context_async(context_obj):
    """Install popup prevention on an async BrowserContext.
    
    Attaches a page handler that installs prevention on all new pages.
    """
    if not _PREVENT_NEW_TABS:
        return
    
    try:
        if hasattr(context_obj, 'on'):
            def _page_handler(page):
                # Schedule async installation
                import asyncio
                try:
                    asyncio.create_task(_install_popup_prevention_on_page_async(page))
                    if _PREVENT_TABS_LOG:
                        logger.info(f"Scheduled async popup prevention on new page {id(page)}")
                except Exception as e:
                    if _PREVENT_TABS_LOG:
                        logger.warning(f"Failed to schedule async popup prevention: {e}")
            
            context_obj.on("page", _page_handler)
            if _PREVENT_TABS_LOG:
                logger.info(f"Popup prevention page handler installed on async context {id(context_obj)}")
    except Exception as e:
        logger.warning(f"Failed to configure popup prevention on async context: {e}")


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
    
    def _inject_debug_args(args: list, browser_name: str) -> tuple:
        """Inject remote debugging flags for Chromium-based browsers.
        
        Returns:
            tuple: (modified_args, chosen_debug_port) where chosen_debug_port is None for non-Chromium browsers
        """
        if browser_name not in ("chromium", "chrome", "msedge"):
            return args, None
        
        args = list(args) if args else []
        
        # Remove existing debug port args if forcing
        if _FORCE_DEBUG_PORT:
            args = [arg for arg in args if "--remote-debugging-port" not in str(arg)]
            args = [arg for arg in args if "--remote-debugging-address" not in str(arg)]
        
        # Check if debug port already set (after potential removal)
        has_debug = any("--remote-debugging-port" in str(arg) for arg in args)
        chosen_port = None
        if not has_debug:
            # Find a free port dynamically
            chosen_port = _find_free_debug_port(_DEBUG_PORT)
            args.extend([
                "--remote-debugging-address=127.0.0.1",
                f"--remote-debugging-port={chosen_port}"
            ])
            logger.debug(f"Injected remote debugging flags (port {chosen_port})")
        else:
            # Port was already set by user, extract it
            for arg in args:
                if "--remote-debugging-port" in str(arg):
                    try:
                        chosen_port = int(str(arg).split("=")[1])
                    except:
                        chosen_port = _DEBUG_PORT
                    break
        
        # Add flags to keep background/occluded tabs rendering
        args.extend([
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling",
        ])
        
        return args, chosen_port
    
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
        
        # Inject debug args for Chromium and capture chosen port
        debug_port = None
        if "args" in kwargs:
            kwargs["args"], debug_port = _inject_debug_args(kwargs["args"], browser_name)
        elif browser_name in ("chromium", "chrome", "msedge"):
            kwargs["args"], debug_port = _inject_debug_args([], browser_name)
        
        browser = _orig_sync_launch(self, *args, **kwargs)
        
        # Store browser info with the actual debug port used
        if browser_name in ("chromium", "chrome", "msedge"):
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
        
        # Inject debug args for Chromium and capture chosen port
        debug_port = None
        if "args" in kwargs:
            kwargs["args"], debug_port = _inject_debug_args(kwargs["args"], browser_name)
        elif browser_name in ("chromium", "chrome", "msedge"):
            kwargs["args"], debug_port = _inject_debug_args([], browser_name)
        
        context = _orig_sync_launch_persistent(self, user_data_dir, *args, **kwargs)
        
        # Set debug port for Chromium (use the port we chose)
        if browser_name in ("chromium", "chrome", "msedge"):
            # Sanity check: read DevToolsActivePort file if available
            import time
            time.sleep(0.5)  # Give Chrome time to write the file
            detected_port = _read_devtools_port(Path(user_data_dir))
            if detected_port and detected_port != debug_port:
                logger.warning(f"DevToolsActivePort mismatch: configured={debug_port}, detected={detected_port}")
                # Use detected port if it differs (Chrome may have chosen different port)
                debug_port = detected_port
            
            logger.info(f"Chromium persistent context launched with debug port {debug_port}")
        
        _browser_info[id(context)] = {
            "browser": browser_name if browser_name in ("chromium", "firefox", "webkit") else "chromium",
            "debug_port": debug_port
        }
        
        # Install popup prevention on persistent context
        _install_popup_prevention_on_context(context)
        # Install on any existing pages
        try:
            for page in context.pages:
                _install_popup_prevention_on_page(page)
        except Exception as e:
            logger.debug(f"Could not install popup prevention on persistent context pages: {e}")
        
        return context
    
    SyncBrowserType.launch_persistent_context = _patched_sync_launch_persistent
    
    # === Popup/Tab prevention patches ===
    
    # Import Browser and BrowserContext classes
    try:
        from playwright.sync_api import Browser as SyncBrowser, BrowserContext as SyncBrowserContext
    except ImportError:
        logger.debug("Could not import sync Browser/BrowserContext for popup prevention")
        SyncBrowser = None
        SyncBrowserContext = None
    
    # Patch sync BrowserContext.new_page
    if SyncBrowserContext:
        _orig_sync_context_new_page = SyncBrowserContext.new_page
        
        def _patched_sync_context_new_page(self, *args, **kwargs):
            page = _orig_sync_context_new_page(self, *args, **kwargs)
            _install_popup_prevention_on_page(page)
            return page
        
        SyncBrowserContext.new_page = _patched_sync_context_new_page
        logger.debug("Patched sync BrowserContext.new_page for popup prevention")
    
    # Patch sync Browser.new_context
    if SyncBrowser:
        _orig_sync_browser_new_context = SyncBrowser.new_context
        
        def _patched_sync_browser_new_context(self, *args, **kwargs):
            context = _orig_sync_browser_new_context(self, *args, **kwargs)
            _install_popup_prevention_on_context(context)
            return context
        
        SyncBrowser.new_context = _patched_sync_browser_new_context
        logger.debug("Patched sync Browser.new_context for popup prevention")
        
        # Patch sync Browser.new_page (creates implicit context + page)
        _orig_sync_browser_new_page = SyncBrowser.new_page
        
        def _patched_sync_browser_new_page(self, *args, **kwargs):
            page = _orig_sync_browser_new_page(self, *args, **kwargs)
            # Install on page and also on its context for future pages
            _install_popup_prevention_on_page(page)
            if hasattr(page, 'context'):
                _install_popup_prevention_on_context(page.context)
            return page
        
        SyncBrowser.new_page = _patched_sync_browser_new_page
        logger.debug("Patched sync Browser.new_page for popup prevention")
    
    # Import async Browser and BrowserContext classes
    try:
        from playwright.async_api import Browser as AsyncBrowser, BrowserContext as AsyncBrowserContext
    except ImportError:
        logger.debug("Could not import async Browser/BrowserContext for popup prevention")
        AsyncBrowser = None
        AsyncBrowserContext = None
    
    # Patch async BrowserContext.new_page
    if AsyncBrowserContext:
        _orig_async_context_new_page = AsyncBrowserContext.new_page
        
        async def _patched_async_context_new_page(self, *args, **kwargs):
            page = await _orig_async_context_new_page(self, *args, **kwargs)
            await _install_popup_prevention_on_page_async(page)
            return page
        
        AsyncBrowserContext.new_page = _patched_async_context_new_page
        logger.debug("Patched async BrowserContext.new_page for popup prevention")
    
    # Patch async Browser.new_context
    if AsyncBrowser:
        _orig_async_browser_new_context = AsyncBrowser.new_context
        
        async def _patched_async_browser_new_context(self, *args, **kwargs):
            context = await _orig_async_browser_new_context(self, *args, **kwargs)
            _install_popup_prevention_on_context_async(context)
            return context
        
        AsyncBrowser.new_context = _patched_async_browser_new_context
        logger.debug("Patched async Browser.new_context for popup prevention")
        
        # Patch async Browser.new_page (creates implicit context + page)
        _orig_async_browser_new_page = AsyncBrowser.new_page
        
        async def _patched_async_browser_new_page(self, *args, **kwargs):
            page = await _orig_async_browser_new_page(self, *args, **kwargs)
            # Install on page and also on its context for future pages
            await _install_popup_prevention_on_page_async(page)
            if hasattr(page, 'context'):
                _install_popup_prevention_on_context_async(page.context)
            return page
        
        AsyncBrowser.new_page = _patched_async_browser_new_page
        logger.debug("Patched async Browser.new_page for popup prevention")
    
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
