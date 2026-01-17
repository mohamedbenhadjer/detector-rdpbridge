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
import urllib.request
import signal
import atexit
from pathlib import Path
from typing import Optional, Any, Dict
from http.server import HTTPServer, BaseHTTPRequestHandler

# Only activate if explicitly enabled
if os.environ.get("MINIAGENT_ENABLED", "1") != "1":
    sys.exit(0)

# Define specific error for agent intervention
class NeedsAgentInterventionError(Exception):
    """Error raised when a Playwright script needs human/agent intervention."""
    pass

# Inject into builtins so it's available globally without import
import builtins
builtins.NeedsAgentInterventionError = NeedsAgentInterventionError

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
_RESUME_FILE_BASE = os.environ.get("MINIAGENT_RESUME_FILE", "/tmp/miniagent_resume")
_RESUME_FILE = f"{_RESUME_FILE_BASE}_{os.getpid()}"  # Per-process resume file

# Optional HTTP resume endpoint configuration
_RESUME_HTTP_ENABLED = os.environ.get("MINIAGENT_RESUME_HTTP", "0") == "1"
_RESUME_HTTP_HOST = os.environ.get("MINIAGENT_RESUME_HTTP_HOST", "127.0.0.1")
_RESUME_HTTP_PORT_BASE = int(os.environ.get("MINIAGENT_RESUME_HTTP_PORT", "8787"))
_RESUME_HTTP_PORT = _RESUME_HTTP_PORT_BASE  # Will be updated to actual chosen port
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


    return None


# === Process and PID Monitoring ===

def _get_process_tree_linux():
    """Builds a dict of ppid -> list of child pids from /proc (Linux only)."""
    tree = {}
    cmdlines = {}
    try:
        # PIDs are directories in /proc that are all digits
        pids = [pid for pid in os.listdir('/proc') if pid.isdigit()]
        for pid_str in pids:
            try:
                pid = int(pid_str)
                # Read ppid from /proc/pid/stat
                with open(f'/proc/{pid}/stat', 'r') as f:
                    stat = f.read().strip()
                    # stat format: pid (comm) state ppid ...
                    # We skip 'comm' because it can contain spaces and parens.
                    # reliably finding the last ')' is the standard way.
                    r_paren = stat.rfind(')')
                    if r_paren == -1: continue
                    
                    rest = stat[r_paren+1:].split()
                    if len(rest) > 1:
                        ppid = int(rest[1])
                        if ppid not in tree:
                            tree[ppid] = []
                        tree[ppid].append(pid)
                
                # Read cmdline from /proc/pid/cmdline
                try:
                    with open(f'/proc/{pid}/cmdline', 'r') as f:
                        # Cmdline arguments are null-separated
                        cmd = f.read().replace('\0', ' ').strip()
                        cmdlines[pid] = cmd
                except:
                    cmdlines[pid] = ""
                    
            except (FileNotFoundError, PermissionError, ValueError):
                continue
    except Exception as e:
        logger.debug(f"Error scanning /proc: {e}")
        
    return tree, cmdlines

def _get_process_tree_windows():
    """Builds a process tree using wmic (Windows only)."""
    tree = {}
    cmdlines = {}
    try:
        import subprocess
        # Get ProcessId, ParentProcessId, CommandLine
        cmd = 'wmic process get ProcessId,ParentProcessId,CommandLine /FORMAT:csv'
        # Run wmic, suppress window creation on Windows if needed (startupinfo)
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        output = subprocess.check_output(cmd, shell=True, startupinfo=startupinfo, text=True)
        
        lines = output.strip().splitlines()
        # First line is blank or headers. CSV format: Node,CommandLine,ParentProcessId,ProcessId
        # Headers: Node,CommandLine,ParentProcessId,ProcessId
        
        for line in lines:
            if not line.strip(): continue
            parts = line.split(',')
            if len(parts) < 4: continue
            
            # Skip header
            if "ProcessId" in parts[-1] and "ParentProcessId" in parts[-2]:
                continue
                
            try:
                # WMIC CSV sometimes puts the value at the end
                # Format: Node, CommandLine, ParentProcessId, ProcessId
                pid = int(parts[-1])
                ppid = int(parts[-2])
                cmd = parts[1] # This might be truncated if it contains commas? 
                # Actually wmic CSV output is tricky with commas in values.
                # But typically CommandLine is the big string.
                # Let's hope basic split works, or we might need robust CSV parsing.
                # For basic browsing detection, "chrome.exe" usually appears even if split is wrong.
                
                if ppid not in tree:
                    tree[ppid] = []
                tree[ppid].append(pid)
                
                cmdlines[pid] = cmd
            except ValueError:
                continue
                
    except Exception as e:
        logger.debug(f"Error checking processes via wmic: {e}")
        
    return tree, cmdlines

def _get_process_tree():
    """Get process tree for current OS."""
    if os.name == 'posix':
        # Linux/Mac (though Mac /proc is different/non-existent, we assume Linux based on env)
        # If Mac, this would likely fail empty or need psutil. 
        # But User says Linux.
        return _get_process_tree_linux()
    else:
        return _get_process_tree_windows()

def _find_browser_pid(root_pid: int) -> Optional[int]:
    """
    Find the main browser process ID that is a descendant of root_pid.
    We look for 'chrome', 'chromium', 'msedge' with no '--type=' argument (main process usually).
    """
    tree, cmdlines = _get_process_tree()
    
    # BFS traversal
    queue = [root_pid]
    candidates = []
    
    # Safety: avoid infinite loops if cycle in tree (rare)
    visited = {root_pid}
    
    while queue:
        current_pid = queue.pop(0)
        
        # Check current process
        cmd = cmdlines.get(current_pid, "").lower()
        if any(x in cmd for x in ["chrome", "chromium", "msedge", "firefox", "webkit", "safari"]):
            # Heuristic: Main process usually doesn't have --type=renderer etc.
            # But Playwright launches wrapper scripts too.
            candidates.append((current_pid, cmd))
            
        # Add children
        children = tree.get(current_pid, [])
        for child in children:
            if child not in visited:
                visited.add(child)
                queue.append(child)
    
    if not candidates:
        return None
        
    # Filter for main process (no --type=)
    for pid, cmd in candidates:
        if "--type=" not in cmd:
            return pid
            
    # Fallback: return the first candidate (closest to root)
    return candidates[0][0]


def _get_cdp_target_id(debug_port: int, page_url: str) -> Optional[str]:
    """
    Query DevTools Protocol to find target ID matching the page URL.
    
    Args:
        debug_port: The Chrome DevTools remote debugging port
        page_url: The current page URL to match
    
    Returns:
        The CDP target ID if found, None otherwise
    """
    if not debug_port or not page_url:
        return None
    
    try:
        url = f"http://127.0.0.1:{debug_port}/json/list"
        with urllib.request.urlopen(url, timeout=0.5) as response:
            targets = json.loads(response.read().decode())
            
            # Try exact match first
            for target in targets:
                if target.get("type") == "page" and target.get("url") == page_url:
                    logger.debug(f"Found CDP target ID (exact match): {target.get('id')}")
                    return target.get("id")
            
            # Try match ignoring trailing slash
            norm_url = page_url.rstrip("/")
            for target in targets:
                target_url = target.get("url", "").rstrip("/")
                if target.get("type") == "page" and target_url == norm_url:
                    logger.debug(f"Found CDP target ID (normalized match): {target.get('id')}")
                    return target.get("id")
    except Exception as e:
        logger.debug(f"Failed to resolve CDP target ID: {e}")
    
    return None


def _hold_deadline():
    """Compute hold deadline from MINIAGENT_HOLD_SECS env var."""
    if _HOLD_RAW in ("", "forever", "inf"):
        return None
    try:
        return time.time() + float(_HOLD_RAW)
    except Exception:
        return None


def _park_until_resume(reason: str, details: str, page_obj=None):
    """
    Block the process until resume signal, timeout, or browser closed.
    Resume happens when MINIAGENT_RESUME_FILE is created or deadline is reached.
    """
    logger.warning(f"Holding on error ({reason}) - waiting for agent. Resume file: {_RESUME_FILE}")
    deadline = _hold_deadline()
    
    # Get manager for cancellation
    from miniagent_ws import get_support_manager
    manager = get_support_manager()
    
    # Try to resolve browser/context from page_obj if possible
    browser_or_context = None
    
    # Fallback to last active page if not provided
    if not page_obj:
        try:
            global _last_active_page_ref
            if _last_active_page_ref:
                page_obj = _last_active_page_ref()
        except:
            pass

    if page_obj:
        try:
            if hasattr(page_obj, "context"):
                browser_or_context = page_obj.context
                if hasattr(browser_or_context, "browser") and browser_or_context.browser:
                    browser_or_context = browser_or_context.browser
        except:
            pass
    
    
    
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
            
        # Check if request was cancelled (e.g. by signal or browser close callback)
        if manager and not manager.active_request_id:
            logger.info("Support request cancelled; exiting hold.")
            sys.exit(1)
            
        # Check if browser/page is closed
        if page_obj:
            try:
                # If we have a PID, check it first as it's the source of truth
                browser_pid = None
                
                # Try to get PID from browser info if available
                if browser_or_context:
                    # Resolve to browser object if context
                    browser_ref = browser_or_context
                    if hasattr(browser_ref, "browser") and browser_ref.browser:
                        browser_ref = browser_ref.browser
                    
                    if id(browser_ref) in _browser_info:
                         browser_pid = _browser_info[id(browser_ref)].get("pid")
                
                # Perform PID liveness check if we found one
                if browser_pid:
                    try:
                        # os.kill(pid, 0) checks if process exists; raises OSError if not
                        os.kill(browser_pid, 0)
                    except OSError:
                        logger.info(f"Browser process {browser_pid} is gone; cancelling support request.")
                        if manager:
                            manager.cancel_support_request("browser_closed")
                        sys.exit(1)
                
                # Fallback to page.is_closed()
                # We removed the active polling for cancellation here because monitor_page_close
                # should handle it via event. But we can keep a passive check if needed.
                pass
            except Exception:
                pass
        
        # Check if browser is disconnected (secondary check)
        if browser_or_context:
            try:
                # PID check is authoritative, usually.
                if not browser_pid:
                    is_connected = True
                    if hasattr(browser_or_context, "is_connected"):
                        is_connected = browser_or_context.is_connected()
                    
                    if not is_connected:
                         logger.info("Browser disconnected during hold (no PID found); cancelling support request.")
                         if manager:
                             manager.cancel_support_request("browser_closed")
                         sys.exit(1)
            except Exception:
                pass
                
        # Use wait_for_timeout if possible to spin event loop
        did_wait = False
        if page_obj and hasattr(page_obj, "wait_for_timeout"):
            try:
                page_obj.wait_for_timeout(1000)
                did_wait = True
            except Exception:
                # Page might be closed or error during wait
                pass
        
        if not did_wait:
            time.sleep(1.0)


def _handle_signal(signum, frame):
    """Handle termination signals (Ctrl+C, etc)."""
    logger.info(f"Signal {signum} received, cancelling support request...")
    
    try:
        from miniagent_ws import get_support_manager
        manager = get_support_manager()
        if manager:
            manager.cancel_support_request("signal_received")
    except Exception:
        pass
        
    # Exit cleanly
    sys.exit(signum)


def _handle_exit():
    """Handle interpreter exit (normal or exception)."""
    # Only cancel if we have an active request
    # This runs for normal exit, caught exceptions, etc.
    try:
        from miniagent_ws import get_support_manager
        manager = get_support_manager()
        if manager and manager.active_request_id:
            logger.info("Script exiting with active support request, cancelling...")
            manager.cancel_support_request("script_exited")
            # Give a small moment for the socket send to flush if needed
            time.sleep(0.2)
    except Exception:
        pass


atexit.register(_handle_exit)


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
    Uses dynamic port selection to allow multiple processes.
    """
    global _RESUME_HTTP_PORT
    
    if not _RESUME_HTTP_ENABLED:
        return

    if not _RESUME_HTTP_TOKEN:
        logger.error("Resume HTTP enabled but MINIAGENT_RESUME_HTTP_TOKEN is not set; not starting HTTP server")
        return

    # Find a free port dynamically
    chosen_port = _find_free_debug_port(_RESUME_HTTP_PORT_BASE)
    _RESUME_HTTP_PORT = chosen_port
    
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


def _extract_detection_selectors(method_name: str, obj, args: tuple, kwargs: dict) -> tuple:
    """
    Extract success/failure selectors from a Playwright method call.
    
    Args:
        method_name: Name of the method being called (e.g., "click", "fill")
        obj: The Page or Locator object
        args: Positional arguments to the method
        kwargs: Keyword arguments to the method
    
    Returns:
        Tuple of (success_selector, failure_selector) where either can be None
    """
    success_selector = None
    failure_selector = None
    
    try:
        # Determine if obj is a Locator or Page
        is_locator = False
        try:
            # Check if it's a Locator by looking for common Locator attributes
            if hasattr(obj, '_impl_obj') and hasattr(obj._impl_obj, '_selector'):
                is_locator = True
            elif hasattr(obj, '_impl') and hasattr(obj._impl, '_selector'):
                is_locator = True
            elif hasattr(obj, '_selector'):
                is_locator = True
        except:
            pass
        
        if is_locator:
            # For Locator methods, extract the selector from the Locator itself
            try:
                # Try _impl_obj._selector first (sync Locator)
                if hasattr(obj, '_impl_obj') and hasattr(obj._impl_obj, '_selector'):
                    success_selector = obj._impl_obj._selector
                # Try _impl._selector (older Playwright versions or async)
                elif hasattr(obj, '_impl') and hasattr(obj._impl, '_selector'):
                    success_selector = obj._impl._selector
                # Try _selector directly
                elif hasattr(obj, '_selector'):
                    success_selector = obj._selector
                else:
                    # Fallback: parse from repr
                    repr_str = repr(obj)
                    if "locator(" in repr_str.lower():
                        # Try to extract selector from repr like "<Locator frame=<Frame ...> selector='button'>""
                        import re
                        match = re.search(r"selector=['\"]([^'\"]+)['\"]", repr_str)
                        if match:
                            success_selector = match.group(1)
            except:
                pass
        else:
            # For Page methods, check if first arg or 'selector' kwarg contains a selector
            selector_methods = ["click", "fill", "press", "type", "select_option", "check", 
                              "uncheck", "wait_for_selector"]
            
            if method_name in selector_methods:
                # First positional arg is typically the selector
                if args and len(args) > 0 and isinstance(args[0], str):
                    success_selector = args[0]
                elif "selector" in kwargs and isinstance(kwargs["selector"], str):
                    success_selector = kwargs["selector"]
    except:
        pass
    
    return success_selector, failure_selector


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
    
    # Patch Browser context manager to catch NeedsAgentInterventionError
    try:
        from playwright.sync_api import Browser as SyncBrowser
        _orig_browser_close = SyncBrowser.close
        
        def _patched_browser_close(self):
            """Patched close to handle any pending operations."""
            return _orig_browser_close(self)
        
        SyncBrowser.close = _patched_browser_close
        
        # Patch Playwright's context manager __exit__
        try:
            # Try to import the actual context manager class
            from playwright.sync_api._context_manager import PlaywrightContextManager
            _orig_playwright_exit = PlaywrightContextManager.__exit__
            
            def _patched_playwright_exit(self, exc_type, exc_val, exc_tb):
                """Intercept NeedsAgentInterventionError before exiting context."""
                if exc_type and issubclass(exc_type, NeedsAgentInterventionError):
                    # Handle the error here before closing browsers
                    if not getattr(exc_val, "_miniagent_handled", False):
                        logger.info(f"Caught NeedsAgentInterventionError in Playwright context: {exc_val}")
                        
                        # Get context from last active page
                        ctx = _get_support_context()
                        
                        # Use last failure selectors if available
                        global _last_failure_selectors
                        success_selector, failure_selector = _last_failure_selectors
                        
                        # Trigger support request
                        manager.trigger_support_request(
                            reason=exc_type.__name__,
                            details=str(exc_val),
                            browser=ctx["browser"],
                            debug_port=ctx["debug_port"],
                            url=ctx["url"],
                            title=ctx["title"],
                            page_id=ctx["page_id"],
                            resume_endpoint=ctx["resume_endpoint"],
                            success_selector=success_selector,
                            failure_selector=failure_selector,
                            cdp_target_id=ctx["cdp_target_id"]
                        )
                        
                        # Hold if needed (browser stays open during hold)
                        if _MODE == "hold":
                            logger.warning(f"Holding on error - browser will stay open. Resume file: {_RESUME_FILE}")
                            # Resolve page object if available from context
                            page_obj = None
                            if hasattr(exc_val, "page"):
                                page_obj = exc_val.page
                            
                            _park_until_resume(exc_type.__name__, str(exc_val), page_obj)
                            # After resume, suppress the exception and continue
                            return True  # Suppress exception
                        elif _MODE == "swallow":
                            return True  # Suppress exception
                        # For report mode, suppress exception too
                        return True
                
                # For all other exceptions, use original behavior
                return _orig_playwright_exit(self, exc_type, exc_val, exc_tb)
            
            PlaywrightContextManager.__exit__ = _patched_playwright_exit
            logger.debug("Patched PlaywrightContextManager for NeedsAgentInterventionError")
        except ImportError:
            # Fallback: try patching via sync_api if exposed (unlikely for _context_manager)
            logger.debug("Could not import PlaywrightContextManager directly")
        except Exception as e:
            logger.debug(f"Could not patch Playwright context manager: {e}")
            
    except ImportError:
        logger.debug("Could not import Browser for context manager patching")
        
    # Register signal handlers
    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
        # Handle SIGHUP (terminal closed)
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, _handle_signal)
        logger.debug("Registered signal handlers for cancellation")
    except Exception as e:
        logger.warning(f"Failed to register signal handlers: {e}")
    
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
        
        # Add flags to keep background/occluded tabs rendering and start maximized
        args.extend([
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling",
            "--start-maximized"
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
        pid = _find_browser_pid(os.getpid())
        
        if browser_name in ("chromium", "chrome", "msedge"):
            _browser_info[id(browser)] = {
                "browser": browser_name,
                "debug_port": debug_port,
                "pid": pid
            }
            logger.info(f"Chromium launched with debug port {debug_port}, PID {pid}")
        else:
            _browser_info[id(browser)] = {
                "browser": "firefox" if browser_name == "firefox" else "webkit",
                "debug_port": None,
                "pid": pid
            }
        
        # Monitor for browser close
        try:
            from miniagent_ws import get_support_manager
            manager = get_support_manager()
            if manager:
                manager.monitor_browser_close(browser)
        except Exception as e:
            logger.warning(f"Failed to attach browser monitor: {e}")
        
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
        
        # Find browser PID
        pid = _find_browser_pid(os.getpid())
        
        _browser_info[id(context)] = {
            "browser": browser_name if browser_name in ("chromium", "firefox", "webkit") else "chromium",
            "debug_port": debug_port,
            "pid": pid
        }
        
        # Install popup prevention on persistent context
        _install_popup_prevention_on_context(context)
        # Install on any existing pages
        try:
            for page in context.pages:
                _install_popup_prevention_on_page(page)
        except Exception as e:
            logger.debug(f"Could not install popup prevention on persistent context pages: {e}")
        
        # Monitor for browser close (context)
        try:
            from miniagent_ws import get_support_manager
            manager = get_support_manager()
            if manager:
                manager.monitor_browser_close(context)
                # Monitor existing pages too
                for page in context.pages:
                    manager.monitor_page_close(page)
        except Exception as e:
            logger.warning(f"Failed to attach context monitor: {e}")

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
            
            # Monitor page close
            try:
                from miniagent_ws import get_support_manager
                manager = get_support_manager()
                if manager:
                    manager.monitor_page_close(page)
            except Exception:
                pass
                
            return page
        
        SyncBrowserContext.new_page = _patched_sync_context_new_page
        logger.debug("Patched sync BrowserContext.new_page for popup prevention and monitoring")
    
    # Patch sync Browser.new_context
    if SyncBrowser:
        _orig_sync_browser_new_context = SyncBrowser.new_context
        
        def _patched_sync_browser_new_context(self, *args, **kwargs):
            # Force no_viewport=True to allow window processing to handle resize naturally
            if "no_viewport" not in kwargs and "viewport" not in kwargs:
                kwargs["no_viewport"] = True
                logger.debug("Forcing no_viewport=True for natural window resizing")
            
            context = _orig_sync_browser_new_context(self, *args, **kwargs)
            _install_popup_prevention_on_context(context)
            return context
        
        SyncBrowser.new_context = _patched_sync_browser_new_context
        logger.debug("Patched sync Browser.new_context for popup prevention and resizing")
        
        # Patch sync Browser.new_page (creates implicit context + page)
        _orig_sync_browser_new_page = SyncBrowser.new_page
        
        def _patched_sync_browser_new_page(self, *args, **kwargs):
            # Force no_viewport=True to allow window processing to handle resize naturally
            if "no_viewport" not in kwargs and "viewport" not in kwargs:
                kwargs["no_viewport"] = True
                logger.debug("Forcing no_viewport=True for natural window resizing")

            page = _orig_sync_browser_new_page(self, *args, **kwargs)
            # Install on page and also on its context for future pages
            _install_popup_prevention_on_page(page)
            if hasattr(page, 'context'):
                _install_popup_prevention_on_context(page.context)
            
            # Monitor page close
            try:
                from miniagent_ws import get_support_manager
                manager = get_support_manager()
                if manager:
                    manager.monitor_page_close(page)
            except Exception:
                pass

            return page
        
        SyncBrowser.new_page = _patched_sync_browser_new_page
        logger.debug("Patched sync Browser.new_page for popup prevention, resizing and monitoring")
    
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
            
            # Monitor page close
            try:
                from miniagent_ws import get_support_manager
                manager = get_support_manager()
                if manager:
                    manager.monitor_page_close(page)
            except Exception:
                pass
                
            return page
        
        AsyncBrowserContext.new_page = _patched_async_context_new_page
        logger.debug("Patched async BrowserContext.new_page for popup prevention and monitoring")
    
    # Patch async Browser.new_context
    if AsyncBrowser:
        _orig_async_browser_new_context = AsyncBrowser.new_context
        
        async def _patched_async_browser_new_context(self, *args, **kwargs):
            # Force no_viewport=True to allow window processing to handle resize naturally
            if "no_viewport" not in kwargs and "viewport" not in kwargs:
                kwargs["no_viewport"] = True
                logger.debug("Forcing no_viewport=True for natural window resizing")
            
            context = await _orig_async_browser_new_context(self, *args, **kwargs)
            _install_popup_prevention_on_context_async(context)
            return context
        
        AsyncBrowser.new_context = _patched_async_browser_new_context
        logger.debug("Patched async Browser.new_context for popup prevention and resizing")
        
        # Patch async Browser.new_page (creates implicit context + page)
        _orig_async_browser_new_page = AsyncBrowser.new_page
        
        async def _patched_async_browser_new_page(self, *args, **kwargs):
            # Force no_viewport=True to allow window processing to handle resize naturally
            if "no_viewport" not in kwargs and "viewport" not in kwargs:
                kwargs["no_viewport"] = True
                logger.debug("Forcing no_viewport=True for natural window resizing")

            page = await _orig_async_browser_new_page(self, *args, **kwargs)
            # Install on page and also on its context for future pages
            await _install_popup_prevention_on_page_async(page)
            if hasattr(page, 'context'):
                _install_popup_prevention_on_context_async(page.context)
            
            # Monitor page close
            try:
                from miniagent_ws import get_support_manager
                manager = get_support_manager()
                if manager:
                    manager.monitor_page_close(page)
            except Exception:
                pass

            return page
        
        AsyncBrowser.new_page = _patched_async_browser_new_page
        logger.debug("Patched async Browser.new_page for popup prevention, resizing and monitoring")
    
    # === Error interception ===
    
    # Track last active page to provide context for global errors
    import weakref
    global _last_active_page_ref
    _last_active_page_ref = None
    
    # Track last failure selectors to provide context when NeedsAgentInterventionError is raised manually
    global _last_failure_selectors
    _last_failure_selectors = (None, None)
    
    def _get_support_context(page_obj=None) -> Dict[str, Any]:
        """
        Get context for support request (browser, page info, CDP target, etc.).
        Uses provided page_obj or falls back to last active page.
        """
        global _last_active_page_ref
        
        # Resolve page object
        if not page_obj and _last_active_page_ref:
            try:
                page_obj = _last_active_page_ref()
            except:
                pass
        
        # Extract page info
        page_info = _get_page_info(page_obj) if page_obj else {}
        
        # Get browser info
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
            elif page_obj and hasattr(page_obj, "_impl") and hasattr(page_obj._impl, "_browser_type"):
                bt_name = page_obj._impl._browser_type.name
                browser_info["browser"] = bt_name if bt_name in ("firefox", "webkit") else "chromium"
                browser_info["pid"] = None # Can't easily determine pid in fallback
        except Exception:
            pass
        
        # Try to resolve CDP Target ID for Chromium browsers
        cdp_target_id = None
        if browser_info.get("debug_port") and page_info.get("url"):
            cdp_target_id = _get_cdp_target_id(browser_info["debug_port"], page_info["url"])
        
        # Build resume endpoint info if HTTP resume is enabled
        resume_endpoint = None
        if _RESUME_HTTP_ENABLED and _RESUME_HTTP_TOKEN:
            resume_endpoint = {
                "scheme": "http",
                "host": _RESUME_HTTP_HOST,
                "port": _RESUME_HTTP_PORT,
                "path": "/resume",
                "token": _RESUME_HTTP_TOKEN
            }
            
        return {
            "browser": browser_info["browser"],
            "pid": browser_info.get("pid"),
            "debug_port": browser_info.get("debug_port"),
            "url": page_info.get("url"),
            "title": page_info.get("title"),
            "page_id": page_info.get("page_id"),
            "resume_endpoint": resume_endpoint,
            "cdp_target_id": cdp_target_id
        }
    
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
                # Resolve page object from Page or Locator
                page_obj = _resolve_page_obj(self)
                
                # Update last active page
                if page_obj:
                    global _last_active_page_ref
                    try:
                        _last_active_page_ref = weakref.ref(page_obj)
                    except:
                        pass
                
                return orig_method(self, *args, **kwargs)
            except (PlaywrightTimeoutError, PlaywrightError, AssertionError, NeedsAgentInterventionError) as e:
                # Resolve page object again (in case it wasn't resolved before)
                page_obj = _resolve_page_obj(self)
                
                # Get context using helper
                ctx = _get_support_context(page_obj)
                
                # Determine error type
                error_type = type(e).__name__
                error_msg = str(e)[:200]
                
                # Extract detection selectors
                success_selector, failure_selector = _extract_detection_selectors(method_name, self, args, kwargs)
                
                # Store selectors for global error handling (in case user catches this and raises NeedsAgentInterventionError)
                if success_selector or failure_selector:
                    global _last_failure_selectors
                    _last_failure_selectors = (success_selector, failure_selector)
                
                # Build details string including selectors for human readability
                details = f"{method_name}: {error_msg}"
                if success_selector:
                    details += f" | successSelector={success_selector}"
                if failure_selector:
                    details += f" | failureSelector={failure_selector}"
                
                # Trigger support request
                if isinstance(e, NeedsAgentInterventionError):
                    manager.trigger_support_request(
                        reason=error_type,
                        details=details,
                        browser=ctx["browser"],
                        debug_port=ctx["debug_port"],
                        url=ctx["url"],
                        title=ctx["title"],
                        page_id=ctx["page_id"],
                        resume_endpoint=ctx["resume_endpoint"],
                        success_selector=success_selector,
                        failure_selector=failure_selector,
                        cdp_target_id=ctx["cdp_target_id"]
                    )
                    # Mark as handled so global hook doesn't re-trigger
                    e._miniagent_handled = True
                    
                    # Handle based on mode (only for NeedsAgentInterventionError)
                    if _MODE == "hold":
                        _park_until_resume(error_type, error_msg, page_obj)
                        # DON'T re-raise - return None to continue (keeps browser open)
                        return None
                    if _MODE == "swallow":
                        # DON'T re-raise - return None to continue
                        return None
                    # For report mode: DON'T re-raise, just return None
                    return None
                
                # For other errors (not NeedsAgentInterventionError), always re-raise
                raise
        
        async def _async_wrapper(self, *args, **kwargs):
            try:
                # Resolve page object from Page or Locator
                page_obj = _resolve_page_obj(self)
                
                # Update last active page
                if page_obj:
                    global _last_active_page_ref
                    try:
                        _last_active_page_ref = weakref.ref(page_obj)
                    except:
                        pass

                return await orig_method(self, *args, **kwargs)
            except (PlaywrightTimeoutError, PlaywrightError, AssertionError, NeedsAgentInterventionError) as e:
                # Resolve page object again
                page_obj = _resolve_page_obj(self)
                
                # Get context using helper
                ctx = _get_support_context(page_obj)
                
                error_type = type(e).__name__
                error_msg = str(e)[:200]
                
                # Extract detection selectors
                success_selector, failure_selector = _extract_detection_selectors(method_name, self, args, kwargs)
                
                # Store selectors for global error handling (in case user catches this and raises NeedsAgentInterventionError)
                if success_selector or failure_selector:
                    global _last_failure_selectors
                    _last_failure_selectors = (success_selector, failure_selector)
                
                # Build details string including selectors for human readability
                details = f"{method_name}: {error_msg}"
                if success_selector:
                    details += f" | successSelector={success_selector}"
                if failure_selector:
                    details += f" | failureSelector={failure_selector}"
                
                if isinstance(e, NeedsAgentInterventionError):
                    manager.trigger_support_request(
                        reason=error_type,
                        details=details,
                        browser=ctx["browser"],
                        debug_port=ctx["debug_port"],
                        url=ctx["url"],
                        title=ctx["title"],
                        page_id=ctx["page_id"],
                        resume_endpoint=ctx["resume_endpoint"],
                        success_selector=success_selector,
                        failure_selector=failure_selector,
                        cdp_target_id=ctx["cdp_target_id"]
                    )
                    # Mark as handled so global hook doesn't re-trigger
                    e._miniagent_handled = True
                    
                    # Handle based on mode (only for NeedsAgentInterventionError)
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
                                
                            # Check if page is closed - handled by event listener now
                            # But we keep a check just in case the event listener failed or wasn't attached
                            # However, user requested to make it like "when no hold is there"
                            # The event listener in SupportRequestManager calls cancel_support_request
                            # which sets active_request_id to None, helping us exit the loop.
                            pass
                                    
                            await asyncio.sleep(1.0)
                    
                    if _MODE == "swallow":
                        return None
                    # For report mode: DON'T re-raise, just return None
                    return None
                
                # For other errors (not NeedsAgentInterventionError), always re-raise
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

def _handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception hook to catch NeedsAgentInterventionError."""
    
    if issubclass(exc_type, NeedsAgentInterventionError) and not getattr(exc_value, "_miniagent_handled", False):
        try:
            from miniagent_ws import get_support_manager
            manager = get_support_manager()
            if manager:
                # Get context from last active page
                ctx = _get_support_context()
                
                # Use last failure selectors if available
                global _last_failure_selectors
                success_selector, failure_selector = _last_failure_selectors
                
                manager.trigger_support_request(
                    reason=exc_type.__name__,
                    details=str(exc_value),
                    browser=ctx["browser"],
                    debug_port=ctx["debug_port"],
                    url=ctx["url"],
                    title=ctx["title"],
                    page_id=ctx["page_id"],
                    resume_endpoint=ctx["resume_endpoint"],
                    success_selector=success_selector,
                    failure_selector=failure_selector,
                    cdp_target_id=ctx["cdp_target_id"]
                )
                
                # Handle based on mode (hold/swallow for NeedsAgentInterventionError)
                if _MODE == "hold":
                    # Get page_obj from weakref if possible
                    page_obj = None
                    if _last_active_page_ref:
                        try:
                            page_obj = _last_active_page_ref()
                        except:
                            pass
                            
                    _park_until_resume(exc_type.__name__, str(exc_value), page_obj)
                    # Don't call original excepthook - we handled it
                    return
                if _MODE == "swallow":
                    # Don't call original excepthook - suppress the error
                    return
        except Exception as e:
            # Don't let our hook crash the app
            logger.error(f"Exception in global hook: {e}")
            pass
    
    # For all other cases, call the original excepthook (prints traceback and exits)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = _handle_exception
