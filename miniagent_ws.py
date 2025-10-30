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
                    time.sleep(self.reconnect_delay - (now - self.last_connect_attempt))
                
                self.last_connect_attempt = time.time()
                logger.info(f"Connecting to {self.ws_url}...")
                
                self.ws = WebSocketApp(
                    self.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                
                self.ws.run_forever()
                
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            # Backoff before reconnecting
            time.sleep(self.reconnect_delay)
            self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    def _on_open(self, ws):
        """Handle WebSocket open - send hello."""
        logger.info("WebSocket connected, sending hello...")
        self.connected = True
        
        hello_msg = {
            "type": "hello",
            "token": self.token,
            "client": self.client_name,
            "version": self.version
        }
        
        try:
            ws.send(json.dumps(hello_msg))
        except Exception as e:
            logger.error(f"Failed to send hello: {e}")
            self.connected = False
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "hello_ack":
                logger.info("Handshake complete")
                self.authenticated = True
                self.reconnect_delay = 0.5  # Reset backoff on success
                self._flush_pending()
            
            elif msg_type == "support_request_ack":
                request_id = data.get("requestId")
                room_id = data.get("roomId")
                logger.info(f"Support request acknowledged: {request_id} (room: {room_id})")
            
            elif msg_type == "error":
                error_code = data.get("code")
                error_msg = data.get("message", "Unknown error")
                logger.error(f"Server error: {error_code} - {error_msg}")
                
                if error_code == "BAD_AUTH":
                    logger.error("Authentication failed - check MINIAGENT_TOKEN")
                    self.authenticated = False
                elif error_code == "NO_USER":
                    logger.warning("No signed-in user - will retry later")
            
            elif msg_type == "pong":
                pass  # Heartbeat response
            
            else:
                logger.debug(f"Received: {data}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {error}")
        self.connected = False
        self.authenticated = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.connected = False
        self.authenticated = False
    
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
                    self.pending_messages.insert(0, msg)
                    break
    
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
                    self.pending_messages.append(msg)
            else:
                logger.info("Not authenticated yet, buffering support request")
                self.pending_messages.append(msg)
    
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
        self.run_id = str(uuid.uuid4())[:8]
        self.pid = os.getpid()
    
    def trigger_support_request(
        self,
        reason: str,
        details: str,
        browser: str = "chromium",
        debug_port: Optional[int] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
        page_id: Optional[str] = None
    ):
        """
        Trigger a support request with deduplication.
        
        Args:
            reason: Error type/category (e.g., "TimeoutError")
            details: Detailed error message
            browser: Browser type ("chromium", "firefox", "webkit")
            debug_port: Remote debugging port (Chromium only)
            url: Current page URL
            title: Current page title
            page_id: Unique page identifier for deduplication
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
        
        if url and not self.redact_urls:
            control_target["urlContains"] = url[:100]  # Truncate long URLs
        
        if title and not self.redact_urls:
            control_target["titleContains"] = title[:100]
        
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
        
        logger.info(f"Triggering support request: {reason}")
        self.ws_client.send_support_request(payload)


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


