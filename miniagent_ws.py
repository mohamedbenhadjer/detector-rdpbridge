"""
MiniAgent WebSocket client for sending support requests to Flutter app.
Handles hello handshake, reconnection with backoff, and buffered sends.
"""
import asyncio
import json
import logging
import os
import time
import uuid
import sys
import random
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Set, Tuple
import threading
import websocket
from websocket import WebSocketApp

logger = logging.getLogger("miniagent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(handler)


class MiniAgentWSClient:
    """WebSocket client with auto-reconnect and buffering."""
    
    def __init__(self, ws_url: str, token: str, client_name: str = "python-cdp-monitor"):
        self.ws_url = ws_url
        self.token = token
        self.client_name = client_name
        self.version = "1.0"
        
        self.ws: Optional[WebSocketApp] = None
        self.connected = False
        self.authenticated = False
        self.pending_messages = []
        self.lock = threading.Lock()
        self.ws_thread: Optional[threading.Thread] = None
        
        # Backoff state
        self.reconnect_delay = 0.5
        self.max_reconnect_delay = 8.0
        self.last_connect_attempt = 0
        
        # Start connection in background
        self._start_connection()
    
    def _start_connection(self):
        """Start WebSocket connection in a background thread."""
        if self.ws_thread and self.ws_thread.is_alive():
            return
        
        self.ws_thread = threading.Thread(target=self._run_ws, daemon=True)
        self.ws_thread.start()
    
    def _run_ws(self):
        """Run WebSocket connection with auto-reconnect."""
        while True:
            try:
                now = time.time()
                if now - self.last_connect_attempt < self.reconnect_delay:
                    actual_delay = self.reconnect_delay - (now - self.last_connect_attempt)
                    jittered_delay = actual_delay * (0.5 + random.random())
                    time.sleep(jittered_delay)

                self.last_connect_attempt = time.time()
                logger.debug(f"Connecting to {self.ws_url}...")

                self.ws = WebSocketApp(
                    self.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )

                self.ws.run_forever(ping_interval=30, ping_timeout=10)

            except Exception as e:
                logger.error(f"WebSocket error: {e}")

            # Backoff before reconnecting
            jittered_delay = self.reconnect_delay * (0.5 + random.random())
            time.sleep(jittered_delay)
            self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    def _on_open(self, ws):
        """Handle WebSocket open - send hello."""
        logger.info(f"WebSocket connection opened to {self.ws_url}")
        logger.debug("Sending hello handshake...")
        self.connected = True
        
        hello_msg = {
            "type": "hello",
            "token": self.token,
            "client": self.client_name,
            "version": self.version
        }
        
        try:
            ws.send(json.dumps(hello_msg))
            logger.info("Hello message sent successfully")
        except Exception as e:
            logger.error(f"Failed to send hello: {e}")
            self.connected = False
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "hello_ack":
                logger.info("Handshake complete - Client Authenticated")
                self.authenticated = True
                self.reconnect_delay = 0.5  # Reset backoff on success

                # Check for active request and verify its status
                global _support_manager
                if _support_manager and _support_manager.active_request_id:
                    self.send_status_check(_support_manager.active_request_id)

                self._flush_pending()

            elif msg_type == "status_result":
                run_id = data.get("runId")
                status = data.get("status")
                logger.info(f"Status check result for {run_id}: {status}")
                if status in ["completed", "failed", "cancelled", "noAgents", "error", "unknown"]:
                    if _support_manager and _support_manager.active_request_id == run_id:
                        logger.info(f"Request {run_id} is {status}, cancelling locally.")
                        with _support_manager.active_request_lock:
                            _support_manager.active_request_id = None
                            _support_manager.active_page_id = None

            elif msg_type == "support_request_ack":
                request_id = data.get("requestId")
                room_id = data.get("roomId")
                logger.info(f"Support request acknowledged: {request_id} (room: {room_id})")
            
            elif msg_type == "error":
                error_code = data.get("code")
                error_msg = data.get("message", "Unknown error")
                logger.error(f"Server error received: {error_code} - {error_msg}")

                if error_code == "BAD_AUTH":
                    logger.error("Authentication failed - check MINIAGENT_TOKEN")
                    self.authenticated = False
                elif error_code == "NO_USER":
                    logger.warning("No signed-in user - will retry later")
                elif error_code == "SERVER_BUSY":
                    logger.warning("Server is busy - backing off")
                    if ws:
                        ws.close()
            
            elif msg_type == "pong":
                # Heartbeat response - debug level only
                logger.debug("Received pong")
            
            else:
                logger.debug(f"Received message type: {msg_type}")
                if "payload" in data:
                    logger.debug(f"Payload: {data['payload']}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e} | Raw message: {message[:100]}...")
            
    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error occurred: {error}")
        self.connected = False
        self.authenticated = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        logger.info(f"WebSocket connection closed. Code: {close_status_code}, Msg: {close_msg}")
        self.connected = False
        self.authenticated = False
    
    def _queue_pending_message(self, msg, insert_front=False):
        """Add a message to the pending queue, capping at 10 to prevent OOM."""
        if insert_front:
            self.pending_messages.insert(0, msg)
        else:
            self.pending_messages.append(msg)
            
        # Cap at 10 messages, dropping the oldest if necessary
        if len(self.pending_messages) > 10:
            dropped = self.pending_messages.pop(0)
            logger.warning(f"Pending messages queue full (cap=10), dropping oldest message of type: {dropped.get('type')}")
    
    def _flush_pending(self):
        """Send any pending messages after authentication."""
        with self.lock:
            if not self.authenticated or not self.ws:
                return
            
            while self.pending_messages:
                msg = self.pending_messages.pop(0)
                try:
                    self.ws.send(json.dumps(msg))
                    logger.debug(f"Sent pending message: {msg.get('type')}")
                except Exception as e:
                    logger.error(f"Failed to send pending message: {e}")
                    self._queue_pending_message(msg, insert_front=True)
                    break
    
    def send_status_check(self, run_id: str):
        """Send a status check request to the server."""
        msg = {
            "type": "status_check",
            "runId": run_id
        }

        with self.lock:
            if self.authenticated and self.ws:
                try:
                    self.ws.send(json.dumps(msg))
                    logger.debug(f"Sent status check for runId: {run_id}")
                except Exception as e:
                    logger.error(f"Failed to send status check: {e}")
                    self._queue_pending_message(msg)
            else:
                logger.debug("Not authenticated yet, buffering status check")
                self._queue_pending_message(msg)

    def send_support_request(self, payload: Dict[str, Any]):
        """
        Send a support request to the Flutter server.
        
        Args:
            payload: Dict with 'description', 'controlTarget', 'meta'
        """
        msg = {
            "type": "support_request",
            "payload": payload
        }
        
        with self.lock:
            if self.authenticated and self.ws:
                try:
                    self.ws.send(json.dumps(msg))
                    logger.info(f"Sent support request: {payload.get('description', 'N/A')[:80]}")
                except Exception as e:
                    logger.error(f"Failed to send support request: {e}")
                    self._queue_pending_message(msg)
            else:
                logger.info("Not authenticated yet, buffering support request")
                self._queue_pending_message(msg)
    
    def send_support_cancelled(self, payload: Dict[str, Any]):
        """
        Send a cancellation message for a support request.
        """
        msg = {
            "type": "support_cancelled",
            "payload": payload
        }

        with self.lock:
            if self.authenticated and self.ws:
                try:
                    self.ws.send(json.dumps(msg))
                    logger.info(f"Sent cancellation: {payload.get('reason', 'N/A')}")
                except Exception as e:
                    logger.error(f"Failed to send cancellation: {e}")
                    self._queue_pending_message(msg)
            else:
                logger.info("Not authenticated yet, buffering cancellation")
                self._queue_pending_message(msg)
    
    def close(self):
        """Close the WebSocket connection."""
        if self.ws:
            self.ws.close()


class SupportRequestManager:
    """Manages support request triggers with deduplication and cooldown."""
    
    def __init__(self, ws_client: MiniAgentWSClient, cooldown_sec: int = 0, redact_urls: bool = False):
        self.ws_client = ws_client
        self.cooldown_sec = cooldown_sec
        self.redact_urls = redact_urls
        
        # Track recent triggers: (runId, page_id) -> timestamp
        self.recent_triggers: Dict[Tuple[str, str], float] = {}
        self.lock = threading.Lock()
        
        # Generate a unique run ID for this process
        self.run_id = str(uuid.uuid4())
        self.pid = os.getpid()
        
        # Track active request for cancellation
        self.active_request_id: Optional[str] = None
        self.active_page_id: Optional[str] = None
        self.active_request_lock = threading.Lock()

    def monitor_browser_close(self, browser):
        """
        Attach a listener to the Playwright browser to cancel the request
        if the browser is closed (disconnected).
        
        Args:
            browser: The Playwright Browser instance.
        """
        def on_disconnected(b):
            logger.info("Browser disconnected, cancelling active support request...")
            self.cancel_support_request("browser_closed")
            
        browser.on("disconnected", on_disconnected)
    
    def monitor_page_close(self, page):
        """
        Attach a listener to the Playwright page to cancel the request
        if the page is closed.

        Args:
            page: The Playwright Page instance.
        """
        page_id = str(id(page))
        def on_close(p):
            logger.info(f"Page closed, checking if active support request should be cancelled... (page_id: {page_id})")
            self.cancel_support_request("page_closed", page_id=page_id)

        page.on("close", on_close)
    
    def trigger_support_request(
        self,
        reason: str,
        details: str,
        browser: str = "chromium",
        debug_port: Optional[int] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
        page_id: Optional[str] = None,
        resume_endpoint: Optional[Dict[str, Any]] = None,
        success_selector: Optional[str] = None,
        failure_selector: Optional[str] = None,
        cdp_target_id: Optional[str] = None
    ):
        """
        Trigger a support request with deduplication.
        """
        page_id = page_id or "default"
        
        with self.lock:
            # Check cooldown
            key = (self.run_id, page_id)
            now = time.time()
            
            if key in self.recent_triggers:
                elapsed = now - self.recent_triggers[key]
                if elapsed < self.cooldown_sec:
                    logger.debug(f"Cooldown active ({elapsed:.1f}s < {self.cooldown_sec}s), skipping duplicate")
                    return
            
            self.recent_triggers[key] = now
            
            # Clean old entries (older than 2x cooldown)
            cutoff = now - (self.cooldown_sec * 2)
            self.recent_triggers = {k: v for k, v in self.recent_triggers.items() if v > cutoff}
        
        # Build payload
        description = f"{reason}: {details}"
        
        control_target = {"browser": browser}
        
        if debug_port is not None:
            control_target["debugPort"] = debug_port
        
        if cdp_target_id is not None:
            control_target["targetId"] = cdp_target_id
        
        if url and not self.redact_urls:
            control_target["urlContains"] = url[:100]  # Truncate long URLs
        
        if title and not self.redact_urls:
            control_target["titleContains"] = title[:100]
            
        if resume_endpoint is not None:
            control_target["resumeEndpoint"] = resume_endpoint
        
        meta = {
            "runId": self.run_id,
            "pid": self.pid,
            "reason": reason,
            "ts": datetime.now(timezone.utc).isoformat()
        }
        
        payload = {
            "description": description[:500],  # Limit description length
            "controlTarget": control_target,
            "meta": meta
        }
        
        # Add detection selectors if provided
        if success_selector is not None or failure_selector is not None:
            detection = {}
            if success_selector is not None:
                detection["successSelector"] = success_selector
            if failure_selector is not None:
                detection["failureSelector"] = failure_selector
            payload["detection"] = detection
            
        # Log with targetId if present for verification
        log_msg = f"Triggering support request: {reason}"
        if cdp_target_id:
            log_msg += f" (targetId: {cdp_target_id})"
        logger.info(log_msg)
        
        with self.active_request_lock:
            self.active_request_id = self.run_id
            self.active_page_id = page_id

        self.ws_client.send_support_request(payload)

    def cancel_support_request(self, reason: str, page_id: Optional[str] = None):
        """
        Cancel the current active support request if any.
        """
        with self.active_request_lock:
            if not self.active_request_id:
                return

            if page_id is not None and self.active_page_id is not None:
                if page_id != self.active_page_id:
                    logger.debug(f"Ignoring cancel request from page {page_id} because active page is {self.active_page_id}")
                    return

            # Send cancellation
            payload = {
                "runId": self.active_request_id,
                "reason": reason,
                "ts": datetime.now(timezone.utc).isoformat()
            }

            self.ws_client.send_support_cancelled(payload)
            self.active_request_id = None
            self.active_page_id = None


# Global singleton instances
_ws_client: Optional[MiniAgentWSClient] = None
_support_manager: Optional[SupportRequestManager] = None


def get_support_manager() -> Optional[SupportRequestManager]:
    """Get or create the global SupportRequestManager."""
    global _ws_client, _support_manager
    
    if _support_manager:
        return _support_manager
    
    # Read config from env
    ws_url = os.environ.get("MINIAGENT_WS_URL", "ws://127.0.0.1:8777/ws")
    token = os.environ.get("MINIAGENT_TOKEN", "")
    client_name = os.environ.get("MINIAGENT_CLIENT", "python-cdp-monitor")
    cooldown_sec = int(os.environ.get("MINIAGENT_COOLDOWN_SEC", "0"))
    redact_urls = os.environ.get("MINIAGENT_REDACT_URLS", "0") == "1"
    
    if not token:
        logger.warning("MINIAGENT_TOKEN not set - support requests disabled")
        return None
    
    try:
        _ws_client = MiniAgentWSClient(ws_url, token, client_name)
        _support_manager = SupportRequestManager(_ws_client, cooldown_sec, redact_urls)
        logger.info(f"MiniAgent initialized (runId: {_support_manager.run_id})")
        return _support_manager
    except Exception as e:
        logger.error(f"Failed to initialize MiniAgent: {e}")
        return None
