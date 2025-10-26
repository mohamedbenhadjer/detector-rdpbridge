"""
Playwright Python injector (sitecustomize) to ensure Chromium exposes a CDP port
and persists the ws URL for the watchdog. Requires setting PYTHONPATH to include
this directory so Python auto-imports sitecustomize at startup.

Usage examples:
  Linux/macOS:
    PYTHONPATH=/absolute/path/to/injectors/pw_py_inject PWDEBUG=1 pytest

  Windows (PowerShell):
    $env:PYTHONPATH = "C:\\absolute\\path\\to\\injectors\\pw_py_inject"; $env:PWDEBUG = "1"; pytest
"""
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict


def _env_true(name: str) -> bool:
    v = os.environ.get(name)
    return str(v).lower() in {"1", "true", "yes", "on"}


WATCHDOG_DIR = Path.home() / ".pw_watchdog"
CDP_DIR = WATCHDOG_DIR / "cdp"
CDP_DIR.mkdir(parents=True, exist_ok=True)


def _get_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _fetch_ws_url(port: int) -> str | None:
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        return data.get("webSocketDebuggerUrl")
    except Exception:
        return None


def _write_cdp(port: int) -> None:
    info: Dict[str, Any] = {"port": port, "wsUrl": _fetch_ws_url(port)}
    try:
        (CDP_DIR / f"{os.getpid()}.json").write_text(json.dumps(info), encoding="utf-8")
    except Exception:
        pass


def _patch_sync_api():
    try:
        from playwright import sync_api as pw_sync  # type: ignore
    except Exception:
        return

    orig_launch = pw_sync.BrowserType.launch
    orig_launch_persist = pw_sync.BrowserType.launch_persistent_context

    def ensure_opts(kwargs: Dict[str, Any]) -> tuple[Dict[str, Any], int | None]:
        opts = dict(kwargs)
        args = list(opts.get("args", []))
        port = None
        if not any("--remote-debugging-port" in str(a) for a in args):
            port = _get_free_port()
            args.append(f"--remote-debugging-port={port}")
        if _env_true("PWDEBUG") and "headless" not in opts:
            opts["headless"] = False
        opts["args"] = args
        return opts, port

    def patched_launch(self, **kwargs):  # type: ignore
        if getattr(self, "name", "") != "chromium":
            return orig_launch(self, **kwargs)
        opts, port = ensure_opts(kwargs)
        browser = orig_launch(self, **opts)
        if port:
            _write_cdp(port)
        return browser

    def patched_launch_persist(self, user_data_dir, **kwargs):  # type: ignore
        if getattr(self, "name", "") != "chromium":
            return orig_launch_persist(self, user_data_dir, **kwargs)
        opts, port = ensure_opts(kwargs)
        ctx = orig_launch_persist(self, user_data_dir, **opts)
        if port:
            _write_cdp(port)
        return ctx

    try:
        pw_sync.BrowserType.launch = patched_launch  # type: ignore
        pw_sync.BrowserType.launch_persistent_context = patched_launch_persist  # type: ignore
    except Exception:
        pass


def _patch_async_api():
    try:
        from playwright import async_api as pw_async  # type: ignore
    except Exception:
        return

    orig_launch = pw_async.BrowserType.launch
    orig_launch_persist = pw_async.BrowserType.launch_persistent_context

    def ensure_opts(kwargs: Dict[str, Any]) -> tuple[Dict[str, Any], int | None]:
        opts = dict(kwargs)
        args = list(opts.get("args", []))
        port = None
        if not any("--remote-debugging-port" in str(a) for a in args):
            port = _get_free_port()
            args.append(f"--remote-debugging-port={port}")
        if _env_true("PWDEBUG") and "headless" not in opts:
            opts["headless"] = False
        opts["args"] = args
        return opts, port

    async def patched_launch(self, **kwargs):  # type: ignore
        if getattr(self, "name", "") != "chromium":
            return await orig_launch(self, **kwargs)
        opts, port = ensure_opts(kwargs)
        browser = await orig_launch(self, **opts)
        if port:
            _write_cdp(port)
        return browser

    async def patched_launch_persist(self, user_data_dir, **kwargs):  # type: ignore
        if getattr(self, "name", "") != "chromium":
            return await orig_launch_persist(self, user_data_dir, **kwargs)
        opts, port = ensure_opts(kwargs)
        ctx = await orig_launch_persist(self, user_data_dir, **opts)
        if port:
            _write_cdp(port)
        return ctx

    try:
        pw_async.BrowserType.launch = patched_launch  # type: ignore
        pw_async.BrowserType.launch_persistent_context = patched_launch_persist  # type: ignore
    except Exception:
        pass


try:
    if not _env_true("PW_WATCHDOG_DISABLE"):
        _patch_sync_api()
        _patch_async_api()
except Exception:
    # Never break the user's run
    pass


