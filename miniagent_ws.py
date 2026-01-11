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
import signal
import sys
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
                logger.debug(f"Connecting to {self.ws_url}...")
                
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
                self._flush_pending()
            
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
                    # No buffering for cancellation - if it fails, it fails
            else:
                logger.info("Not authenticated, cannot send cancellation")
    
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
        
        # Track active request for cancellation
        self.active_request_id: Optional[str] = None
        self.active_request_lock = threading.Lock()
        
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Set up signal handlers to cancel pending requests on exit."""
        def handler(signum, frame):
            sig_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
            logger.info(f"Received {sig_name}, cancelling active support requests...")
            
            # Cancel support request
            self.cancel_support_request("signal_received")
            
            # Close WebSocket
            self.ws_client.close()
            
            # Exit
            sys.exit(0)
            
        try:
            signal.signal(signal.SIGINT, handler)
            signal.signal(signal.SIGTERM, handler)
            if hasattr(signal, "SIGHUP"):
                signal.signal(signal.SIGHUP, handler)
        except ValueError:
            # Handles case where not running in main thread
            logger.warning("Could not setup signal handlers (not main thread?)")
    
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
            
        self.ws_client.send_support_request(payload)

    def cancel_support_request(self, reason: str):
        """
        Cancel the current active support request if any.
        """
        with self.active_request_lock:
            if not self.active_request_id:
                return
            
            # Send cancellation
            payload = {
                "runId": self.active_request_id,
                "reason": reason,
                "ts": datetime.now(timezone.utc).isoformat()
            }
            
            self.ws_client.send_support_cancelled(payload)
            self.active_request_id = None


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
