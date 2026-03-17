#!/usr/bin/env python3
"""
Stress Test v2 — Headless Browser Clients

Launches real headless Chromium browsers via Playwright, each opening google.com
and triggering a support request through the miniagent WebSocket bridge.

Usage:
    cd /home/mohamed/detector-rdpbridge
    source myenv/bin/activate
    MINIAGENT_TOKEN=<token> python stress_browser_clients.py --count 5
    MINIAGENT_TOKEN=<token> python stress_browser_clients.py --count 20 --batch-size 5

Set MINIAGENT_TOKEN env var to your real token before running.
Optionally set MINIAGENT_WS_URL (default: ws://127.0.0.1:8777/ws).
"""

import argparse
import asyncio
import json
import os
import signal
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

# ─── Configuration ────────────────────────────────────────────────────────────

WS_URL = os.environ.get("MINIAGENT_WS_URL", "ws://127.0.0.1:8777/ws")
TOKEN = os.environ.get("MINIAGENT_TOKEN", "")
BASE_DEBUG_PORT = 9300

# ─── State ────────────────────────────────────────────────────────────────────

_browsers = []       # Track all open browser instances
_shutdown = False     # Global shutdown flag


def _find_free_port(start: int) -> int:
    """Find a free port starting from `start`."""
    for offset in range(100):
        port = start + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    return start


async def _get_cdp_target_id(debug_port: int) -> Optional[str]:
    """Resolve the CDP target ID for the main page."""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://127.0.0.1:{debug_port}/json/list",
                timeout=aiohttp.ClientTimeout(total=2),
            ) as resp:
                if resp.status == 200:
                    targets = await resp.json()
                    for t in targets:
                        if t.get("type") == "page":
                            return t.get("id")
    except Exception:
        pass
    return None


async def _run_browser(worker_id: int, debug_port: int, console, hold_time: float):
    """Launch a single headless browser, navigate to google.com, send support request.

    The WebSocket connection is kept alive for the entire hold period so the
    server does not interpret a client disconnect as a cancellation.
    """
    from playwright.async_api import async_playwright
    import websockets

    status = {"id": worker_id, "state": "launching", "port": debug_port}

    try:
        async with async_playwright() as p:
            console.print(f"  [cyan]Browser {worker_id}[/] → Launching on port {debug_port}...")
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    f"--remote-debugging-port={debug_port}",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--disable-background-timer-throttling",
                    "--no-sandbox",
                ],
            )
            _browsers.append(browser)
            status["state"] = "navigating"

            page = await browser.new_page()
            await page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=30000)
            page_url = page.url
            page_title = await page.title()
            status["state"] = "loaded"
            console.print(f"  [green]Browser {worker_id}[/] → google.com loaded ({page_title})")

            # Resolve CDP target ID
            target_id = await _get_cdp_target_id(debug_port)
            status["target_id"] = target_id

            # ── Open WS and keep it alive for hold duration ──────────────
            status["state"] = "sending_request"
            run_id = str(uuid.uuid4())[:8]
            t0 = time.time()
            ws = None

            try:
                ws = await websockets.connect(
                    WS_URL,
                    open_timeout=30,
                    close_timeout=5,
                    max_size=1024 * 1024,
                )

                # Hello handshake
                await ws.send(json.dumps({
                    "type": "hello",
                    "token": TOKEN,
                    "client": f"stress-browser-{worker_id}",
                    "version": "1.0",
                }))
                ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                if ack.get("type") != "hello_ack":
                    console.print(
                        f"  [bold red]Browser {worker_id}[/] → ❌ Auth failed: {ack}"
                    )
                    status["state"] = "failed"
                    return status

                # Build and send support request
                control_target = {
                    "browser": "chromium",
                    "debugPort": debug_port,
                    "urlContains": page_url[:100],
                    "titleContains": page_title[:100],
                }
                if target_id:
                    control_target["targetId"] = target_id

                await ws.send(json.dumps({
                    "type": "support_request",
                    "payload": {
                        "description": f"Stress browser {worker_id}: needs agent on google.com",
                        "controlTarget": control_target,
                        "meta": {
                            "runId": run_id,
                            "pid": os.getpid(),
                            "reason": "NeedsAgentInterventionError",
                            "ts": datetime.now(timezone.utc).isoformat(),
                        },
                    },
                }))

                # Wait for ack
                resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                elapsed = time.time() - t0
                success = resp.get("type") == "support_request_ack"

                if success:
                    console.print(
                        f"  [bold green]Browser {worker_id}[/] → ✅ Request sent "
                        f"(req={resp.get('requestId', '?')[:8]}, "
                        f"room={resp.get('roomId', '?')[:8]}, "
                        f"{int(elapsed * 1000)}ms)"
                    )
                    status["state"] = "waiting"
                    status["request_id"] = resp.get("requestId")
                else:
                    console.print(
                        f"  [bold red]Browser {worker_id}[/] → ❌ Unexpected response: {resp.get('type')}"
                    )
                    status["state"] = "failed"

                # ── Hold: keep BOTH the browser AND the WS open ──────────
                if not _shutdown and status["state"] == "waiting":
                    try:
                        await asyncio.sleep(hold_time)
                    except asyncio.CancelledError:
                        pass

            except Exception as e:
                console.print(
                    f"  [bold red]Browser {worker_id}[/] → ❌ WS error: {e}"
                )
                status["state"] = "failed"
                status["error"] = str(e)[:120]
            finally:
                # Close WS *before* closing browser
                if ws:
                    try:
                        await ws.close()
                    except Exception:
                        pass

            # Cleanup browser
            status["state"] = "closing"
            try:
                await browser.close()
            except Exception:
                pass
            if browser in _browsers:
                _browsers.remove(browser)

            return status

    except asyncio.CancelledError:
        status["state"] = "cancelled"
        return status
    except Exception as e:
        console.print(f"  [bold red]Browser {worker_id}[/] → 💥 Error: {e}")
        status["state"] = "error"
        status["error"] = str(e)[:120]
        return status


async def _run_test(count: int, batch_size: int, delay: float, hold_time: float):
    """Main test runner."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    console.print()
    console.print(Panel.fit(
        f"[bold cyan]STRESS TEST v2 — HEADLESS BROWSER CLIENTS[/]\n"
        f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]",
        border_style="cyan",
    ))
    console.print()
    console.print(f"  Target WS:     [yellow]{WS_URL}[/]")
    console.print(f"  Token:         [yellow]{TOKEN[:8]}...[/]")
    console.print(f"  Browsers:      [bold]{count}[/]")
    console.print(f"  Batch size:    [bold]{batch_size}[/]")
    console.print(f"  Batch delay:   [bold]{delay}s[/]")
    console.print(f"  Hold time:     [bold]{hold_time}s[/]")
    console.print()

    # Assign ports
    used_ports = set()
    ports = []
    for i in range(count):
        port = _find_free_port(BASE_DEBUG_PORT + len(used_ports))
        while port in used_ports:
            port = _find_free_port(port + 1)
        used_ports.add(port)
        ports.append(port)

    all_tasks = []
    all_results = []
    n_batches = (count + batch_size - 1) // batch_size

    console.print(f"[bold]1️⃣  Launching {count} browsers in {n_batches} batches...[/]\n")
    t_start = time.time()

    for batch_idx in range(n_batches):
        if _shutdown:
            break

        start = batch_idx * batch_size
        end = min(start + batch_size, count)

        console.print(f"[dim]── Batch {batch_idx + 1}/{n_batches} (browsers {start}–{end - 1}) ──[/]")

        # Create tasks for this batch and add to all_tasks
        # We don't await them here so they can hold in the background
        tasks = [
            asyncio.create_task(_run_browser(i, ports[i], console, hold_time))
            for i in range(start, end)
        ]
        all_tasks.extend(tasks)

        if batch_idx < n_batches - 1 and not _shutdown:
            console.print(f"  [dim]Waiting {delay}s before next batch...[/]")
            await asyncio.sleep(delay)

    # Now we wait for ALL created tasks (across all batches) to finish their hold time
    if all_tasks:
        console.print(f"\n[dim]All {count} browsers launched. Waiting for their hold times to complete...[/]")
        results = await asyncio.gather(*all_tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, dict):
                all_results.append(r)

    t_done = time.time()
    total_seconds = t_done - t_start

    # Summary
    success_count = sum(1 for r in all_results if r.get("state") == "waiting" or r.get("request_id"))
    fail_count = len(all_results) - success_count

    console.print()
    console.print(Panel.fit(
        f"[bold]RESULTS[/]\n\n"
        f"  Total time:  {total_seconds:.2f}s\n"
        f"  ✅ Sent:     {success_count}/{count}\n"
        f"  ❌ Failed:   {fail_count}/{count}",
        border_style="green" if fail_count == 0 else "yellow",
    ))
    console.print()


async def _shutdown_browsers():
    """Gracefully close all open browsers."""
    global _shutdown
    _shutdown = True
    for browser in list(_browsers):
        try:
            await browser.close()
        except Exception:
            pass
    _browsers.clear()


def main():
    if not TOKEN:
        print("❌ ERROR: MINIAGENT_TOKEN env var is required")
        print("   Set it to the same token your host app expects.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Stress Test v2 — Launch headless browsers with support requests"
    )
    parser.add_argument("--count", "-n", type=int, default=5,
                        help="Number of browsers to launch (default: 5)")
    parser.add_argument("--batch-size", "-b", type=int, default=5,
                        help="Browsers per batch (default: 5)")
    parser.add_argument("--delay", "-d", type=float, default=2.0,
                        help="Delay between batches in seconds (default: 2.0)")
    parser.add_argument("--hold", type=float, default=300.0,
                        help="How long to hold browsers open in seconds (default: 300)")
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Handle Ctrl+C
    def _signal_handler(sig, frame):
        print("\n⚠️  Ctrl+C received, shutting down browsers...")
        loop.create_task(_shutdown_browsers())

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        loop.run_until_complete(_run_test(args.count, args.batch_size, args.delay, args.hold))
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted, cleaning up...")
        loop.run_until_complete(_shutdown_browsers())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
