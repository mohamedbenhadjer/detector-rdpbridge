#!/usr/bin/env python3
"""
Stress Test v2 — Agent Simulator (Interactive TUI)

Simulates multiple support agents that sign up via Supabase Auth, go online,
watch for pending support requests, and auto-accept them.

Interactive terminal menu for controlling agent count, viewing logs,
inspecting live sessions, and cleanup.

Usage:
    cd /home/mohamed/detector-rdpbridge
    source myenv/bin/activate
    SUPABASE_URL=https://tfbrkdiowzzkhgtdmxlj.supabase.co \
    SUPABASE_ANON_KEY=<key> \
    python stress_agent_simulator.py

Environment variables:
    SUPABASE_URL       — Supabase project URL
    SUPABASE_ANON_KEY  — Supabase anon/publishable key
    AGENT_PASSWORD     — Password for test agents (default: StressTest2026!)
    POLL_INTERVAL      — Seconds between queue polls (default: 3)
"""

import asyncio
import json
import os
import signal
import sys
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from typing import Optional

# ─── Configuration ────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tfbrkdiowzzkhgtdmxlj.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
AGENT_PASSWORD = os.environ.get("AGENT_PASSWORD", "StressTest2026!")
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "3"))
HEARTBEAT_INTERVAL = 25  # seconds, matching the Flutter app

# ─── Global State ─────────────────────────────────────────────────────────────

class AgentState:
    """Tracks state for a single simulated agent."""
    def __init__(self, index: int):
        self.index = index
        self.email = f"stressagent{index}_{uuid.uuid4().hex[:6]}@test.local"
        self.name = f"StressAgent-{index}"
        self.agent_id = uuid.uuid4().hex[:8]
        self.device_id = uuid.uuid4().hex
        self.user_id: Optional[str] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.status = "created"  # created → signing_up → online → watching → accepted → error
        self.accepted_count = 0
        self.last_accepted_request: Optional[str] = None
        self.last_accepted_room: Optional[str] = None
        self.error: Optional[str] = None
        self.task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self.logs: list[str] = []

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {msg}")
        # Keep last 100 log lines
        if len(self.logs) > 100:
            self.logs = self.logs[-100:]

    def stop(self):
        self._stop_event.set()

    @property
    def stopped(self) -> bool:
        return self._stop_event.is_set()


_agents: list[AgentState] = []
_global_logs: list[str] = []
_shutdown = False


def _global_log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    _global_logs.append(entry)
    if len(_global_logs) > 500:
        _global_logs[:] = _global_logs[-500:]


# ─── Supabase HTTP helpers (no SDK dependency, just aiohttp) ──────────────────

async def _supabase_request(
    method: str,
    path: str,
    body: Optional[dict] = None,
    access_token: Optional[str] = None,
    is_auth: bool = False,
) -> dict:
    """Make a request to Supabase REST or Auth API."""
    import aiohttp

    if is_auth:
        url = f"{SUPABASE_URL}/auth/v1{path}"
    else:
        url = f"{SUPABASE_URL}/rest/v1{path}"

    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    elif not is_auth:
        headers["Authorization"] = f"Bearer {SUPABASE_ANON_KEY}"

    async with aiohttp.ClientSession() as session:
        kwargs = {"headers": headers}
        if body is not None:
            kwargs["json"] = body

        async with session.request(method, url, **kwargs) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise Exception(f"Supabase error {resp.status}: {text[:200]}")
            if text.strip():
                return json.loads(text)
            return {}


async def _supabase_rpc(
    function_name: str,
    params: dict,
    access_token: str,
) -> dict:
    """Call a Supabase RPC function."""
    import aiohttp

    url = f"{SUPABASE_URL}/rest/v1/rpc/{function_name}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=params) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise Exception(f"RPC {function_name} error {resp.status}: {text[:200]}")
            if text.strip():
                return json.loads(text)
            return {}


# ─── Agent Lifecycle ──────────────────────────────────────────────────────────

async def _agent_signup(agent: AgentState):
    """Sign up a new agent via Supabase Auth."""
    agent.status = "signing_up"
    agent.log(f"Signing up as {agent.email}...")

    result = await _supabase_request("POST", "/signup", {
        "email": agent.email,
        "password": AGENT_PASSWORD,
        "data": {"full_name": agent.name},
    }, is_auth=True)

    agent.user_id = result.get("user", {}).get("id") or result.get("id")
    agent.access_token = result.get("access_token")
    agent.refresh_token = result.get("refresh_token")

    if not agent.user_id:
        raise Exception(f"No user_id returned: {result}")

    if not agent.access_token:
        # Some Supabase configs require email confirmation, try sign in
        agent.log("No token from signup (email confirm?), attempting sign in...")
        login_result = await _supabase_request("POST", "/token?grant_type=password", {
            "email": agent.email,
            "password": AGENT_PASSWORD,
        }, is_auth=True)
        agent.access_token = login_result.get("access_token")
        agent.refresh_token = login_result.get("refresh_token")
        agent.user_id = login_result.get("user", {}).get("id") or agent.user_id

    agent.log(f"✅ Signed up (user_id={agent.user_id[:8]}...)")


async def _agent_register(agent: AgentState):
    """Register the agent in the agents table."""
    agent.log("Registering in agents table...")

    agent_data = {
        "id": agent.user_id,
        "name": agent.name,
        "email": agent.email,
        "phone": "",
        "agent_id": agent.agent_id,
        "role": "agent",
        "skills": [],
        "is_online": False,
        "device_type": "linux",
    }

    # Upsert into agents table
    import aiohttp
    url = f"{SUPABASE_URL}/rest/v1/agents"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {agent.access_token}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=agent_data) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise Exception(f"Register failed {resp.status}: {text[:200]}")

    agent.log(f"✅ Registered (agent_id={agent.agent_id})")


async def _agent_go_online(agent: AgentState):
    """Set agent online via RPC."""
    agent.log("Going online...")

    result = await _supabase_rpc("set_device_online", {
        "p_device_id": agent.device_id,
        "p_device_name": "Linux PC (Stress Test)",
        "p_device_type": "linux",
    }, agent.access_token)

    if result and result.get("success"):
        agent.status = "online"
        agent.log(f"✅ Online (device={agent.device_id[:8]}...)")
    else:
        raise Exception(f"set_device_online failed: {result}")


async def _agent_heartbeat(agent: AgentState):
    """Send heartbeat to keep agent online."""
    try:
        await _supabase_rpc("touch_device_last_seen", {
            "p_device_id": agent.device_id,
        }, agent.access_token)
        agent.log("💓 Heartbeat sent")
    except Exception as e:
        agent.log(f"⚠️ Heartbeat failed: {e}")


async def _agent_poll_and_accept(agent: AgentState):
    """Poll for pending support requests and auto-accept the first one found."""
    import aiohttp

    url = (
        f"{SUPABASE_URL}/rest/v1/support_requests"
        f"?status=eq.pending&order=created_at.asc&limit=1"
    )
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {agent.access_token}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status >= 400:
                text = await resp.text()
                agent.log(f"⚠️ Poll failed: {text[:100]}")
                return

            data = await resp.json()
            if not data:
                return  # No pending requests

    request = data[0]
    request_id = request["id"]
    room_id = request.get("room_id", "")

    agent.log(f"📥 Found pending request: {request_id[:8]}...")
    agent.status = "accepting"

    try:
        result = await _supabase_rpc("accept_support_request", {
            "p_request_id": request_id,
            "p_agent_id": agent.user_id,
            "p_agent_name": agent.name,
        }, agent.access_token)

        agent.accepted_count += 1
        agent.last_accepted_request = request_id
        agent.last_accepted_room = room_id
        agent.status = "accepted"
        agent.log(f"✅ Accepted request {request_id[:8]}! (total: {agent.accepted_count})")
        _global_log(f"Agent {agent.name} accepted request {request_id[:8]}")

    except Exception as e:
        error_str = str(e)
        if "no longer pending" in error_str.lower() or "state" in error_str.lower():
            agent.log(f"⏭️ Request {request_id[:8]} already taken, will retry...")
        else:
            agent.log(f"❌ Accept failed: {e}")
        agent.status = "watching"


async def _agent_go_offline(agent: AgentState):
    """Set agent offline via RPC."""
    try:
        await _supabase_rpc("set_device_offline", {
            "p_device_id": agent.device_id,
        }, agent.access_token)
        agent.log("🔴 Offline")
    except Exception as e:
        agent.log(f"⚠️ Offline failed: {e}")


async def _agent_loop(agent: AgentState):
    """Main loop for a single agent: signup → register → online → poll → accept."""
    try:
        await _agent_signup(agent)
        await _agent_register(agent)
        await _agent_go_online(agent)

        agent.status = "watching"
        last_heartbeat = time.time()

        while not agent.stopped:
            # Heartbeat every HEARTBEAT_INTERVAL seconds
            if time.time() - last_heartbeat >= HEARTBEAT_INTERVAL:
                await _agent_heartbeat(agent)
                last_heartbeat = time.time()

            # Poll for pending requests
            await _agent_poll_and_accept(agent)

            # After accepting, go back to watching
            if agent.status == "accepted":
                agent.status = "watching"

            # Wait before next poll
            try:
                await asyncio.wait_for(agent._stop_event.wait(), timeout=POLL_INTERVAL)
                break  # Stop event was set
            except asyncio.TimeoutError:
                pass  # Continue polling

    except Exception as e:
        agent.status = "error"
        agent.error = str(e)[:200]
        agent.log(f"💥 Error: {e}")
        _global_log(f"Agent {agent.name} error: {e}")

    finally:
        await _agent_go_offline(agent)
        agent.status = "stopped"


# ─── Cleanup ──────────────────────────────────────────────────────────────────

async def _cleanup_agents():
    """Delete all test agents from the agents table."""
    import aiohttp

    cleaned = 0
    for agent in _agents:
        if not agent.user_id or not agent.access_token:
            continue

        try:
            url = f"{SUPABASE_URL}/rest/v1/agents?id=eq.{agent.user_id}"
            headers = {
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {agent.access_token}",
            }
            async with aiohttp.ClientSession() as session:
                # Delete from agent_devices first
                dev_url = f"{SUPABASE_URL}/rest/v1/agent_devices?agent_id=eq.{agent.user_id}"
                async with session.delete(dev_url, headers=headers) as resp:
                    pass

                # Delete from agents
                async with session.delete(url, headers=headers) as resp:
                    if resp.status < 400:
                        cleaned += 1
        except Exception:
            pass

    return cleaned


# ─── Interactive TUI ──────────────────────────────────────────────────────────

def _print_menu(console):
    """Print the interactive menu."""
    from rich.panel import Panel
    from rich.table import Table

    # Agent status table
    table = Table(title="Active Agents", show_lines=True)
    table.add_column("#", style="bold", width=4)
    table.add_column("Name", width=18)
    table.add_column("Status", width=12)
    table.add_column("Accepted", width=9, justify="right")
    table.add_column("Last Request", width=12)
    table.add_column("Email", width=35, style="dim")

    for agent in _agents:
        status_color = {
            "watching": "green",
            "online": "cyan",
            "accepting": "yellow",
            "accepted": "bold green",
            "error": "red",
            "stopped": "dim",
            "signing_up": "cyan",
        }.get(agent.status, "white")

        table.add_row(
            str(agent.index),
            agent.name,
            f"[{status_color}]{agent.status}[/]",
            str(agent.accepted_count),
            (agent.last_accepted_request or "—")[:12],
            agent.email,
        )

    if _agents:
        console.print(table)

    total_accepted = sum(a.accepted_count for a in _agents)
    active = sum(1 for a in _agents if a.status in ("watching", "accepting", "accepted", "online"))

    console.print()
    console.print(Panel.fit(
        f"  Active: [bold]{active}[/]/{len(_agents)}    "
        f"Total accepted: [bold green]{total_accepted}[/]\n\n"
        f"  [bold][1][/] Spawn N agents\n"
        f"  [bold][2][/] Stop all agents\n"
        f"  [bold][3][/] View logs\n"
        f"  [bold][4][/] View agent session (open browser)\n"
        f"  [bold][5][/] Cleanup (delete test agents)\n"
        f"  [bold][q][/] Quit",
        title="[bold cyan]AGENT SIMULATOR[/]",
        border_style="cyan",
    ))


async def _spawn_agents(count: int, console):
    """Spawn N new agents."""
    start_idx = len(_agents)
    for i in range(count):
        agent = AgentState(start_idx + i)
        _agents.append(agent)
        agent.task = asyncio.create_task(_agent_loop(agent))
        _global_log(f"Spawned agent {agent.name}")
    console.print(f"  [green]Spawned {count} agents (total: {len(_agents)})[/]")


async def _stop_all_agents(console):
    """Stop all running agents."""
    for agent in _agents:
        agent.stop()
    # Wait for all tasks to complete
    tasks = [a.task for a in _agents if a.task and not a.task.done()]
    if tasks:
        console.print(f"  [yellow]Waiting for {len(tasks)} agents to stop...[/]")
        await asyncio.gather(*tasks, return_exceptions=True)
    console.print("  [green]All agents stopped.[/]")


def _view_logs(console):
    """Show recent global logs."""
    from rich.panel import Panel

    if not _global_logs:
        console.print("  [dim]No logs yet.[/]")
        return

    # Show last 20 lines
    recent = _global_logs[-20:]
    console.print(Panel("\n".join(recent), title="Recent Logs", border_style="blue"))

    # Option to view specific agent logs
    console.print()
    agent_idx = input("  View agent logs? Enter agent # (or Enter to skip): ").strip()
    if agent_idx.isdigit():
        idx = int(agent_idx)
        matching = [a for a in _agents if a.index == idx]
        if matching:
            agent = matching[0]
            logs = agent.logs[-30:] if agent.logs else ["No logs"]
            console.print(Panel(
                "\n".join(logs),
                title=f"Logs: {agent.name}",
                border_style="magenta",
            ))
        else:
            console.print(f"  [red]Agent #{idx} not found.[/]")


def _view_session(console):
    """Open a browser to view an agent's session."""
    # List agents with accepted requests
    agents_with_sessions = [a for a in _agents if a.last_accepted_request]

    if not agents_with_sessions:
        console.print("  [yellow]No agents have accepted sessions yet.[/]")
        return

    from rich.table import Table

    table = Table(title="Agents with Sessions")
    table.add_column("#", width=4)
    table.add_column("Name", width=18)
    table.add_column("Last Request", width=38)
    table.add_column("Room ID", width=38)
    table.add_column("Accepted", justify="right", width=9)

    for agent in agents_with_sessions:
        table.add_row(
            str(agent.index),
            agent.name,
            agent.last_accepted_request or "—",
            agent.last_accepted_room or "—",
            str(agent.accepted_count),
        )

    console.print(table)
    console.print()

    choice = input("  Enter agent # to view session (or Enter to skip): ").strip()
    if not choice.isdigit():
        return

    idx = int(choice)
    matching = [a for a in agents_with_sessions if a.index == idx]
    if not matching:
        console.print(f"  [red]Agent #{idx} not found.[/]")
        return

    agent = matching[0]

    # Try to find the debug port of the browser that made this request
    # by checking the support_requests table for the room_id
    # and looking for the browser's CDP endpoint
    if agent.last_accepted_room:
        # The room_id corresponds to a browser's debug port
        # We try to find the browser that generated this request
        console.print(f"  [cyan]Opening session viewer for {agent.name}...[/]")
        console.print(f"  Room: {agent.last_accepted_room}")
        console.print(f"  Request: {agent.last_accepted_request}")

        # Check Supabase for session details
        console.print()
        console.print("  [dim]Looking for CDP endpoints from active browsers...[/]")

        # Try common debug ports from the browser stress test
        found_port = None
        for port in range(9300, 9350):
            try:
                import urllib.request
                url = f"http://127.0.0.1:{port}/json/list"
                with urllib.request.urlopen(url, timeout=0.5) as resp:
                    targets = json.loads(resp.read().decode())
                    if targets:
                        found_port = port
                        console.print(f"  [green]Found browser on port {port} with {len(targets)} target(s)[/]")
                        for t in targets:
                            console.print(f"    → {t.get('title', 'untitled')}: {t.get('url', '')[:60]}")
                        break
            except Exception:
                continue

        if found_port:
            devtools_url = f"http://127.0.0.1:{found_port}"
            console.print(f"\n  [bold]DevTools URL: {devtools_url}[/]")
            console.print("  [dim]Opening in browser...[/]")
            webbrowser.open(f"http://localhost:{found_port}/json")
            console.print("  [green]✅ Opened in browser.[/]")
        else:
            console.print("  [yellow]No active browser CDP endpoints found (are browser clients running?).[/]")
            console.print(f"  [dim]Tip: Run stress_browser_clients.py in another terminal first.[/]")
    else:
        console.print("  [yellow]No room ID for this agent's session.[/]")


async def _interactive_loop():
    """Main interactive TUI loop."""
    from rich.console import Console

    console = Console()

    console.print()
    console.print("[bold cyan]━━━ STRESS TEST v2 — AGENT SIMULATOR ━━━[/]")
    console.print(f"  Supabase: [yellow]{SUPABASE_URL}[/]")
    console.print(f"  Poll interval: [yellow]{POLL_INTERVAL}s[/]")
    console.print()

    while not _shutdown:
        _print_menu(console)
        console.print()

        try:
            choice = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("  Choose option: ").strip().lower()
            )
        except (EOFError, KeyboardInterrupt):
            choice = "q"

        console.print()

        if choice == "1":
            count_str = input("  How many agents to spawn? ").strip()
            if count_str.isdigit() and int(count_str) > 0:
                await _spawn_agents(int(count_str), console)
                await asyncio.sleep(2)  # Give agents time to start
            else:
                console.print("  [red]Invalid number.[/]")

        elif choice == "2":
            await _stop_all_agents(console)

        elif choice == "3":
            _view_logs(console)

        elif choice == "4":
            _view_session(console)

        elif choice == "5":
            console.print("  [yellow]Cleaning up test agents...[/]")
            await _stop_all_agents(console)
            cleaned = await _cleanup_agents()
            console.print(f"  [green]Cleaned up {cleaned} agent(s) from database.[/]")
            console.print("  [dim]Note: Auth users cannot be deleted from client side.[/]")

        elif choice == "q":
            console.print("  [yellow]Shutting down...[/]")
            await _stop_all_agents(console)
            break

        else:
            console.print("  [red]Invalid option.[/]")

        console.print()

    console.print("[bold green]Goodbye! 👋[/]")


def main():
    if not SUPABASE_ANON_KEY:
        print("❌ ERROR: SUPABASE_ANON_KEY env var is required")
        print("   Set it to your Supabase project's anon key.")
        sys.exit(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _signal_handler(sig, frame):
        global _shutdown
        _shutdown = True
        print("\n⚠️  Shutting down...")

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        loop.run_until_complete(_interactive_loop())
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted.")
        loop.run_until_complete(_stop_all_agents.__wrapped__(None) if hasattr(_stop_all_agents, '__wrapped__') else asyncio.sleep(0))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
