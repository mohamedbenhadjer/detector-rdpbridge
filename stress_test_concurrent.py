#!/usr/bin/env python3
"""
Stress Test: Launch N pure WebSocket clients, each sending a support
request to the REAL host app simultaneously.

No Playwright required — lightweight enough for 10K+ clients.

Usage:
    cd /home/mohamed/detector-rdpbridge
    MINIAGENT_TOKEN=<token> ./myenv/bin/python stress_test_concurrent.py --count 100
    MINIAGENT_TOKEN=<token> ./myenv/bin/python stress_test_concurrent.py --count 1000 --batch-size 200
    MINIAGENT_TOKEN=<token> ./myenv/bin/python stress_test_concurrent.py --count 10000 --batch-size 500 --ramp-delay 0.1

Set MINIAGENT_TOKEN env var to your real token before running.
Optionally set MINIAGENT_WS_URL (default: ws://127.0.0.1:8777/ws).
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone


# ─── Configuration ───────────────────────────────────────────────────────────

WS_URL = os.environ.get("MINIAGENT_WS_URL", "ws://127.0.0.1:8777/ws")
TOKEN = os.environ.get("MINIAGENT_TOKEN", "")
HEALTH_URL = os.environ.get("MINIAGENT_HEALTH_URL", "http://127.0.0.1:8777/health")


# ─── Error categories ───────────────────────────────────────────────────────

def _categorize_error(error_str: str) -> str:
    """Categorize an error string into a human-readable bucket."""
    if not error_str:
        return "unknown"
    e = error_str.lower()
    if "timeout" in e or "timed out" in e:
        return "timeout"
    if "connection refused" in e or "connect call failed" in e:
        return "connection_refused"
    if "503" in e or "service unavailable" in e or "server_busy" in e:
        return "backpressure_503"
    if "too many" in e:
        return "connection_limit"
    if "auth" in e or "bad_auth" in e or "token" in e:
        return "auth_failed"
    if "reset" in e or "broken pipe" in e or "connection reset" in e:
        return "connection_reset"
    if "eof" in e or "incomplete" in e:
        return "connection_dropped"
    return "other"


# ─── Worker ──────────────────────────────────────────────────────────────────

async def _worker(worker_id: int, barrier: asyncio.Barrier | None, timeout: float):
    """Connect via pure WebSocket, authenticate, send support request."""
    import websockets

    run_id = str(uuid.uuid4())

    # Wait for all workers in the same batch to be ready
    if barrier:
        await barrier.wait()

    t0 = time.time()
    try:
        async with websockets.connect(
            WS_URL,
            open_timeout=timeout,
            close_timeout=5,
            max_size=1024 * 1024,
            compression="deflate",  # Match server-side compression
        ) as ws:
            # Hello handshake
            await ws.send(json.dumps({
                "type": "hello",
                "token": TOKEN,
                "client": f"stress-worker-{worker_id}",
                "version": "1.0",
            }))
            ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            if ack.get("type") != "hello_ack":
                elapsed = time.time() - t0
                return {"id": worker_id, "success": False, "elapsed_ms": int(elapsed * 1000), "error": f"auth_failed: {ack}"}

            # Send support request
            await ws.send(json.dumps({
                "type": "support_request",
                "payload": {
                    "description": f"Stress test worker {worker_id}: needs agent intervention",
                    "controlTarget": {
                        "browser": "chromium",
                        "urlContains": f"stress-test-{worker_id}",
                        "titleContains": f"Worker {worker_id}",
                    },
                    "meta": {
                        "runId": run_id,
                        "pid": os.getpid(),
                        "reason": "NeedsAgentInterventionError",
                        "ts": datetime.now(timezone.utc).isoformat(),
                    },
                },
            }))

            # Wait for ack
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            elapsed = time.time() - t0
            success = resp.get("type") == "support_request_ack"
            error = None if success else f"unexpected_response: {resp.get('type', 'null')}"
            return {"id": worker_id, "success": success, "elapsed_ms": int(elapsed * 1000), "error": error}

    except Exception as e:
        elapsed = time.time() - t0
        return {"id": worker_id, "success": False, "elapsed_ms": int(elapsed * 1000), "error": str(e)[:120]}


# ─── Histogram ───────────────────────────────────────────────────────────────

def _print_histogram(elapsed_times: list[int], width: int = 50):
    """Print an ASCII latency histogram."""
    if not elapsed_times:
        return

    # Create 10 buckets
    min_ms = min(elapsed_times)
    max_ms = max(elapsed_times)
    if max_ms == min_ms:
        max_ms = min_ms + 1

    n_buckets = min(10, len(set(elapsed_times)))
    bucket_size = (max_ms - min_ms) / n_buckets

    buckets = [0] * n_buckets
    for t in elapsed_times:
        idx = min(int((t - min_ms) / bucket_size), n_buckets - 1)
        buckets[idx] += 1

    max_count = max(buckets) if buckets else 1

    print("  Latency Distribution:")
    print()
    for i, count in enumerate(buckets):
        lo = int(min_ms + i * bucket_size)
        hi = int(min_ms + (i + 1) * bucket_size)
        bar_len = int(count / max_count * width)
        bar = "█" * bar_len
        print(f"  {lo:>6}ms - {hi:>6}ms │ {bar} ({count})")
    print()


# ─── Health Check ────────────────────────────────────────────────────────────

async def _check_health():
    """Query the /health endpoint and print server metrics."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(HEALTH_URL, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print("  Server Health:")
                    print(f"    Connections:      {data.get('connections', '?')}")
                    print(f"    Peak connections: {data.get('peak_connections', '?')}")
                    print(f"    Queue depth:      {data.get('queue_depth', '?')}")
                    print(f"    Total received:   {data.get('total_received', '?')}")
                    print(f"    Total completed:  {data.get('total_completed', '?')}")
                    print(f"    Total failed:     {data.get('total_failed', '?')}")
                    print(f"    Backpressured:    {data.get('total_backpressured', '?')}")
                    print(f"    Server p50/p95/p99: {data.get('latency_p50_ms', '?')}/{data.get('latency_p95_ms', '?')}/{data.get('latency_p99_ms', '?')}ms")
                    print()
    except ImportError:
        print("  [aiohttp not installed, skipping health check]")
    except Exception as e:
        print(f"  [Health check failed: {e}]")


# ─── Main ────────────────────────────────────────────────────────────────────

async def _run_test(count: int, batch_size: int, ramp_delay: float, timeout: float):
    print()
    print("=" * 70)
    print(f"  STRESS TEST — {count} PURE WS CLIENTS → HOST APP")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    print(f"  Target:      {WS_URL}")
    print(f"  Token:       {TOKEN[:8]}...")
    print(f"  Batch size:  {batch_size}")
    print(f"  Ramp delay:  {ramp_delay}s between batches")
    print(f"  Timeout:     {timeout}s per worker")
    print()

    # Pre-test health check
    print("0️⃣  Pre-test health check...")
    await _check_health()

    all_results = []
    n_batches = (count + batch_size - 1) // batch_size

    print(f"1️⃣  Firing {count} requests in {n_batches} batches of {batch_size}...")
    print()

    t_start = time.time()

    for batch_idx in range(n_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, count)
        current_batch_size = end - start

        barrier = asyncio.Barrier(current_batch_size)

        tasks = [
            asyncio.create_task(_worker(i, barrier, timeout))
            for i in range(start, end)
        ]

        results = await asyncio.gather(*tasks)
        all_results.extend(results)

        pass_count = sum(1 for r in results if r["success"])
        print(f"   Batch {batch_idx + 1}/{n_batches}: {pass_count}/{current_batch_size} passed", end="")

        if batch_idx < n_batches - 1:
            if ramp_delay > 0:
                print(f" (waiting {ramp_delay}s)...", end="")
                await asyncio.sleep(ramp_delay)
        print()

    t_done = time.time()
    total_seconds = t_done - t_start
    print()
    print(f"   ✅ All {count} requests complete in {total_seconds:.2f}s")

    # Post-test health check
    print()
    print("2️⃣  Post-test health check...")
    await _check_health()

    # Print results
    _print_summary(all_results, total_seconds, count)


def _print_summary(results, total_seconds, count):
    print()
    print("=" * 70)
    print("  RESULTS")
    print("=" * 70)
    print()

    pass_count = sum(1 for r in results if r["success"])
    fail_count = count - pass_count
    elapsed_times = [r["elapsed_ms"] for r in results if r["success"]]
    all_elapsed = [r["elapsed_ms"] for r in results]

    # Latency stats
    if elapsed_times:
        sorted_times = sorted(elapsed_times)
        p50 = statistics.median(sorted_times)
        p95 = sorted_times[min(int(len(sorted_times) * 0.95), len(sorted_times) - 1)]
        p99 = sorted_times[min(int(len(sorted_times) * 0.99), len(sorted_times) - 1)]
        avg = statistics.mean(sorted_times)
        min_ms = min(sorted_times)
        max_ms = max(sorted_times)
    else:
        p50 = p95 = p99 = avg = min_ms = max_ms = 0

    # Throughput
    throughput = pass_count / total_seconds if total_seconds > 0 else 0

    print(f"  Total time:     {total_seconds:.2f}s")
    print(f"  Throughput:     {throughput:.1f} req/s")
    print()
    print(f"  ✅ Passed:      {pass_count}/{count} ({pass_count*100//count if count else 0}%)")
    print(f"  ❌ Failed:      {fail_count}/{count}")
    print()
    print("  Latency (successful requests):")
    print(f"    min:  {min_ms}ms")
    print(f"    avg:  {avg:.0f}ms")
    print(f"    p50:  {p50:.0f}ms")
    print(f"    p95:  {p95}ms")
    print(f"    p99:  {p99}ms")
    print(f"    max:  {max_ms}ms")
    print()

    # Histogram
    _print_histogram(all_elapsed)

    # Error categorization
    failed = [r for r in results if not r["success"]]
    if failed:
        error_cats = Counter(_categorize_error(r.get("error", "")) for r in failed)
        print("-" * 70)
        print(f"  ERROR BREAKDOWN ({len(failed)} failures):")
        print("-" * 70)
        for cat, cnt in error_cats.most_common():
            pct = cnt * 100 // len(failed)
            bar = "█" * min(cnt, 40)
            print(f"  {cat:<25} {cnt:>5} ({pct:>3}%) {bar}")
        print()

        # Show sample errors
        print("  SAMPLE FAILURES (first 10):")
        for r in failed[:10]:
            cat = _categorize_error(r.get("error", ""))
            print(f"  Worker {r['id']:>5}: {r['elapsed_ms']:>5}ms [{cat}] {r.get('error', 'unknown')[:80]}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")
        print()

    if pass_count == count:
        print("  🏆 ALL REQUESTS SUCCEEDED!")
    elif pass_count > count * 0.99:
        print(f"  ⚡ EXCELLENT ({pass_count*100//count}% success rate)")
    elif pass_count > count * 0.95:
        print(f"  ⚡ PASSED ({pass_count*100//count}% success rate)")
    elif pass_count > count * 0.80:
        print(f"  ⚠️  DEGRADED ({pass_count*100//count}% success rate)")
    else:
        print(f"  ❌ FAILED ({pass_count*100//count}% success rate)")

    print()
    print("=" * 70)


def main():
    if not TOKEN:
        print("❌ ERROR: MINIAGENT_TOKEN env var is required")
        print("   Set it to the same token your host app expects.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="WebSocket Stress Test (10K+ capable)")
    parser.add_argument("--count", "-n", type=int, default=100,
                        help="Number of concurrent WS clients (default: 100)")
    parser.add_argument("--batch-size", "-b", type=int, default=0,
                        help="Batch size for ramp-up (default: all at once)")
    parser.add_argument("--ramp-delay", type=float, default=0.5,
                        help="Delay between batches in seconds (default: 0.5)")
    parser.add_argument("--timeout", "-t", type=float, default=30.0,
                        help="Timeout per worker in seconds (default: 30)")
    args = parser.parse_args()

    # If batch-size not specified, fire all at once
    if args.batch_size <= 0:
        args.batch_size = args.count

    asyncio.run(_run_test(args.count, args.batch_size, args.ramp_delay, args.timeout))


if __name__ == "__main__":
    main()
