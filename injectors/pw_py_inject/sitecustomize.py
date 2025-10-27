"""
Python Playwright CDP Injector

Monkey-patches playwright.async_api.BrowserType.launch() and sync_api to force:
- --remote-debugging-port=0 (ephemeral port)
- headless=False (only for Chromium)

Discovers CDP WebSocket URL and writes metadata to ~/.pw_watchdog/cdp/<runId>.json

Usage: PYTHONPATH=/path/to/pw_py_inject pytest
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Watchdog directories
WATCHDOG_DIR = Path(os.getenv('PW_WATCHDOG_DIR', Path.home() / '.pw_watchdog'))
CDP_DIR = WATCHDOG_DIR / 'cdp'

# Ensure CDP directory exists
CDP_DIR.mkdir(parents=True, exist_ok=True)


def get_run_id() -> str:
    """Generate or retrieve runId."""
    if 'PW_WATCHDOG_RUN_ID' in os.environ:
        return os.environ['PW_WATCHDOG_RUN_ID']
    
    # Generate from pid and timestamp
    start_ms = int(time.time() * 1000)
    return f"{os.getpid()}-{start_ms}"


def read_devtools_active_port(user_data_dir: str, max_retries: int = 20, delay: float = 0.5) -> Optional[Dict[str, Any]]:
    """Parse DevToolsActivePort file to get CDP WebSocket URL."""
    active_port_path = Path(user_data_dir) / 'DevToolsActivePort'
    
    for attempt in range(max_retries):
        if active_port_path.exists():
            try:
                content = active_port_path.read_text().strip()
                lines = content.split('\n')
                
                if len(lines) >= 2:
                    port = int(lines[0])
                    ws_endpoint = lines[1]
                    
                    return {
                        'port': port,
                        'wsUrl': f'ws://127.0.0.1:{port}{ws_endpoint}',
                        'devtoolsActivePortPath': str(active_port_path)
                    }
            except (IOError, ValueError):
                pass
        
        time.sleep(delay)
    
    return None


def write_cdp_metadata(run_id: str, cdp_info: Dict[str, Any]):
    """Write CDP metadata to watchdog directory."""
    metadata_path = CDP_DIR / f"{run_id}.json"
    metadata = {
        'runId': run_id,
        **cdp_info,
        'timestamp': time.time()
    }
    
    try:
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"[pw_py_inject] CDP metadata written: {metadata_path}", file=sys.stderr)
    except IOError as e:
        print(f"[pw_py_inject] Failed to write CDP metadata: {e}", file=sys.stderr)


def patch_browser_type_launch():
    """Patch BrowserType.launch() for both sync and async APIs."""
    run_id = get_run_id()
    print(f"[pw_py_inject] Injector loaded, runId: {run_id}", file=sys.stderr)
    
    try:
        # Patch async API
        try:
            from playwright.async_api import BrowserType as AsyncBrowserType
            original_async_launch = AsyncBrowserType.launch
            
            async def patched_async_launch(self, **kwargs):
                browser_name = self.name if hasattr(self, 'name') else 'unknown'
                
                # Only patch Chromium
                if browser_name == 'chromium':
                    print(f"[pw_py_inject] Patching async chromium.launch()", file=sys.stderr)
                    
                    # Force headless: False
                    kwargs['headless'] = False
                    
                    # Add remote debugging port
                    args = kwargs.get('args', [])
                    if not any(arg.startswith('--remote-debugging-port') for arg in args):
                        args.append('--remote-debugging-port=0')
                    kwargs['args'] = args
                    
                    print(f"[pw_py_inject] Launching Chromium with CDP enabled", file=sys.stderr)
                    browser = await original_async_launch(self, **kwargs)
                    
                    # Extract user data dir
                    try:
                        # Access internal properties (may vary by Playwright version)
                        if hasattr(browser, '_impl_obj'):
                            impl = browser._impl_obj
                            if hasattr(impl, '_browser_type') and hasattr(impl._browser_type, '_user_data_dir'):
                                user_data_dir = impl._browser_type._user_data_dir
                            elif hasattr(impl, '_connection') and hasattr(impl._connection, '_user_data_dir'):
                                user_data_dir = impl._connection._user_data_dir
                            else:
                                # Try to get from context
                                contexts = impl._contexts if hasattr(impl, '_contexts') else []
                                if contexts and hasattr(contexts[0], '_user_data_dir'):
                                    user_data_dir = contexts[0]._user_data_dir
                                else:
                                    user_data_dir = None
                            
                            if user_data_dir:
                                # Read CDP info in background
                                import asyncio
                                asyncio.create_task(_read_and_write_cdp_async(user_data_dir, run_id))
                    except Exception as e:
                        print(f"[pw_py_inject] Error extracting CDP info: {e}", file=sys.stderr)
                    
                    return browser
                else:
                    return await original_async_launch(self, **kwargs)
            
            AsyncBrowserType.launch = patched_async_launch
        except ImportError:
            pass
        
        # Patch sync API
        try:
            from playwright.sync_api import BrowserType as SyncBrowserType
            original_sync_launch = SyncBrowserType.launch
            
            def patched_sync_launch(self, **kwargs):
                browser_name = self.name if hasattr(self, 'name') else 'unknown'
                
                # Only patch Chromium
                if browser_name == 'chromium':
                    print(f"[pw_py_inject] Patching sync chromium.launch()", file=sys.stderr)
                    
                    # Force headless: False
                    kwargs['headless'] = False
                    
                    # Add remote debugging port
                    args = kwargs.get('args', [])
                    if not any(arg.startswith('--remote-debugging-port') for arg in args):
                        args.append('--remote-debugging-port=0')
                    kwargs['args'] = args
                    
                    print(f"[pw_py_inject] Launching Chromium with CDP enabled", file=sys.stderr)
                    browser = original_sync_launch(self, **kwargs)
                    
                    # Extract user data dir
                    try:
                        if hasattr(browser, '_impl_obj'):
                            impl = browser._impl_obj
                            user_data_dir = None
                            
                            # Try various paths to get user_data_dir
                            if hasattr(impl, '_browser_type') and hasattr(impl._browser_type, '_user_data_dir'):
                                user_data_dir = impl._browser_type._user_data_dir
                            elif hasattr(impl, '_local_utils') and hasattr(impl._local_utils, '_temp_dir'):
                                # Fallback: check temp dir
                                temp_dir = impl._local_utils._temp_dir
                                if temp_dir:
                                    user_data_dir = temp_dir
                            
                            if user_data_dir:
                                # Read CDP info synchronously
                                import threading
                                threading.Thread(
                                    target=_read_and_write_cdp_sync,
                                    args=(user_data_dir, run_id),
                                    daemon=True
                                ).start()
                    except Exception as e:
                        print(f"[pw_py_inject] Error extracting CDP info: {e}", file=sys.stderr)
                    
                    return browser
                else:
                    return original_sync_launch(self, **kwargs)
            
            SyncBrowserType.launch = patched_sync_launch
        except ImportError:
            pass
        
    except Exception as e:
        print(f"[pw_py_inject] Failed to patch Playwright: {e}", file=sys.stderr)


async def _read_and_write_cdp_async(user_data_dir: str, run_id: str):
    """Read and write CDP info asynchronously."""
    import asyncio
    
    # Run in thread to avoid blocking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _read_and_write_cdp_sync, user_data_dir, run_id)


def _read_and_write_cdp_sync(user_data_dir: str, run_id: str):
    """Read and write CDP info synchronously."""
    cdp_info = read_devtools_active_port(user_data_dir)
    if cdp_info:
        write_cdp_metadata(run_id, cdp_info)
    else:
        print(f"[pw_py_inject] Failed to read CDP info from {user_data_dir}", file=sys.stderr)


# Apply patches on module import
patch_browser_type_launch()


