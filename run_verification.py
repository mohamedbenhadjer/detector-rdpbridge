import asyncio
import websockets
import json
import subprocess
import os
import signal
import time
import sys
from threading import Thread

# Configuration
WS_PORT = 8790
WS_URL = f"ws://127.0.0.1:{WS_PORT}/ws"

# Shared state
received_messages = []
server_running = False

async def echo(websocket):
    global server_running
    server_running = True
    print(f"Server: Client connected")
    try:
        async for message in websocket:
            print(f"Server received: {message}")
            data = json.loads(message)
            received_messages.append(data)
            
            msg_type = data.get("type")
            if msg_type == "hello":
                await websocket.send(json.dumps({"type": "hello_ack"}))
            elif msg_type == "support_request":
                await websocket.send(json.dumps({
                    "type": "support_request_ack", 
                    "requestId": "test-req-1",
                    "roomId": "room-1"
                }))
    except websockets.exceptions.ConnectionClosed:
        print("Server: Client disconnected")

async def start_server():
    print(f"Starting mock WS server on port {WS_PORT}...")
    async with websockets.serve(echo, "127.0.0.1", WS_PORT) as server:
        await asyncio.Future()  # run forever

def run_mock_server_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_server())

def main():
    server_thread = Thread(target=run_mock_server_thread, daemon=True)
    server_thread.start()
    
    # Wait for server to start
    time.sleep(2)
    
    # Use venv python
    python_exe = os.path.join("venv", "bin", "python")
    
    # Run the playwright script with a custom behavior
    # We want to simulate successful resumption and then a random exit
    # But `example_playwright_script` is hardcoded.
    # We can use MINIAGENT_ON_ERROR=hold to make it wait.
    # Then we simulate a resume.
    # Then we KILL / Interrupt the script?
    # Actually `atexit` works on normal exit too. 
    # But `example_playwright_script` closes nicely.
    # Wait, `atexit` will fire on normal exit too. If there is an active request.
    # But if `example_playwright_script` finishes properly, it should NOT have an active request?
    # `SupportRequestManager` only tracks `active_request_id` when triggered.
    # It does NOT clear it on resolution (because we don't know resolution).
    # Ah! The agent assumes that if the script is still running, the request is active?
    # NO. `active_request_id` is set when we send "support_request".
    # It is CLEARED only if we call `cancel_support_request`.
    # It is NEVER cleared on "success".
    # So if the script finishes successfully, `atexit` WILL fire cancel.
    # Is that desired?
    # The user said: "if the support request is already accepted and it's working is this working too or just when it's pending??"
    # If it's accepted (agent joined) -> script is running.
    # If script finishes successfully, the support request is effectively "done".
    # Sending "cancelled" on success might be weird?
    # But `miniagent` has no "resolve" API.
    # If the script exits, the session is over. "Cancelled" (or "Closed") is appropriate.
    # The host app likely treats "Cancelled" as "Session Ended".
    
    env = os.environ.copy()
    env["MINIAGENT_WS_URL"] = WS_URL
    env["MINIAGENT_TOKEN"] = "test-token"
    env["MINIAGENT_ON_ERROR"] = "hold"
    env["MINIAGENT_ENABLED"] = "1"
    
    print("Starting example_playwright_script.py...")
    
    proc = subprocess.Popen(
        [python_exe, "example_playwright_script.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=os.setsid 
    )
    
    # We wait for support request
    start_time = time.time()
    trigger_found = False
    
    while time.time() - start_time < 20:
        if proc.poll() is not None:
            break
        
        # Check messages
        has_req = any(m.get("type") == "support_request" for m in received_messages)
        if has_req and not trigger_found:
            print("\nReceived support request! Sending SIGTERM in 2s...")
            time.sleep(2)
            
            # Send SIGTERM (which is handled by signal handler, which calls cleanup)
            # OR we can let it exit naturally if we could.
            # But here `example_playwright_script` is stuck in `hold` loop.
            # So we MUST kill it or resume it.
            # Let's send SIGTERM. This tests the signal handler + atexit (one of them wins, probably signal handler).
            
            # To test ATEXIT specifically, we need it to NOT satisfy signal handler (SIGINT/SIGTERM).
            # We need to RESUME it, then have it crash or exit.
            
            # Let's try to Resume it via HTTP!
            # We need the resume port. It logs "Resume HTTP server listening on ...".
            # We can't easily parse stdout in real time from here without blocking threads or complicated logic.
            # But the port defaults to 8787 or similar.
            
            # ALTERNATIVE: Just rely on SIGTERM for now.
            # Wait, user asked for "Global Exit Handler" for "Accepted and working".
            # If it's working, it's running code.
            # If I press Ctrl+C, `_handle_signal` catches it.
            # If code raises generic Exception (not Playwright), Python exits -> `atexit`.
            # If code calls `sys.exit()`, `atexit`.
            
            # So `atexit` covers the "sys.exit()" or "unhandled exception" case.
            
            # I will send SIGTERM to verify signal handler behaves correctly with `atexit` registered (idempotency?).
            # Actually, `signal.SIGTERM` calls `sys.exit(signum)`.
            # `sys.exit` triggers `atexit`!
            # So both will run?
            # `_handle_signal` calls `cancel` explicitly.
            # Then exits.
            # Then `atexit` runs `_handle_exit`, which calls `cancel`.
            # `cancel` clears `active_request_id` -> so second call is no-op.
            # Safe.
            
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            trigger_found = True
            break
            
        time.sleep(1)
        
    proc.wait()
    
    print("\n\nMessages received:")
    for msg in received_messages:
        print(f"- {msg.get('type')}: {msg.get('payload', {}).get('reason', 'N/A')}")
        
    # Verify
    has_cancel = any(m.get("type") == "support_cancelled" for m in received_messages)
    if has_cancel:
        print("\nSUCCESS: Received support_cancelled message.")
    else:
        print("\nFAILURE: Did not receive support_cancelled message.")

if __name__ == "__main__":
    main()
