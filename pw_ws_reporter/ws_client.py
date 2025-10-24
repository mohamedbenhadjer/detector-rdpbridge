"""
WebSocket client for communicating with the Flutter app.

This module handles:
- Connection with exponential backoff
- Hello/auth handshake
- Support request sending with ack waiting
- Retry logic
- Optional keepalive pings
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

import websockets
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger("pw_ws_reporter")


# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Environment-based configuration with sensible defaults."""
    
    WS_URL: str = os.getenv("WS_URL", "ws://127.0.0.1:8777/ws")
    IPC_TOKEN: str = os.getenv("IPC_TOKEN", "change-me")
    BROWSER: str = os.getenv("BROWSER", "brave")
    DEBUG_PORT: int = int(os.getenv("DEBUG_PORT", "9222"))
    CONNECT_TIMEOUT_SECONDS: int = int(os.getenv("CONNECT_TIMEOUT_SECONDS", "5"))
    ACK_TIMEOUT_SECONDS: int = int(os.getenv("ACK_TIMEOUT_SECONDS", "5"))
    PW_WS_CAPTURE_SCREENSHOT: bool = os.getenv("PW_WS_CAPTURE_SCREENSHOT", "0") == "1"
    PW_WS_TRACE_PATH: Optional[str] = os.getenv("PW_WS_TRACE_PATH")


# ============================================================================
# Pydantic Message Schemas
# ============================================================================

class HelloMessage(BaseModel):
    """Hello/auth message sent to the Flutter server."""
    type: Literal["hello"] = "hello"
    token: str
    client: Literal["playwright-reporter"] = "playwright-reporter"
    version: Literal["1.0"] = "1.0"


class HelloAck(BaseModel):
    """Acknowledgment from server after successful hello."""
    type: Literal["hello_ack"]


class ControlTarget(BaseModel):
    """Browser control target information for remote debugging."""
    browser: str
    debugPort: int
    urlContains: Optional[str] = None
    titleContains: Optional[str] = None
    targetId: Optional[str] = None


class Meta(BaseModel):
    """Metadata about the test failure."""
    testName: str
    timestamp: str
    screenshotB64: Optional[str] = None
    tracePath: Optional[str] = None


class SupportRequestPayload(BaseModel):
    """Payload for a support request."""
    description: str
    controlTarget: Optional[ControlTarget] = None
    meta: Meta


class SupportRequest(BaseModel):
    """Support request message sent to Flutter server."""
    type: Literal["support_request"] = "support_request"
    payload: SupportRequestPayload


class SupportRequestAck(BaseModel):
    """Acknowledgment from server after processing support request."""
    type: Literal["support_request_ack"]
    roomId: str
    requestId: str


# ============================================================================
# Custom Exceptions
# ============================================================================

class WsClientError(Exception):
    """Base exception for WS client errors."""
    pass


class ConnectionError(WsClientError):
    """Failed to connect to the WebSocket server."""
    pass


class AuthenticationError(WsClientError):
    """Failed to authenticate with the server."""
    pass


class AckTimeoutError(WsClientError):
    """Timeout waiting for acknowledgment."""
    pass


class UnexpectedResponseError(WsClientError):
    """Received unexpected response from server."""
    pass


# ============================================================================
# WebSocket Client
# ============================================================================

class WsClient:
    """
    WebSocket client for communicating with the Flutter app.
    
    This client handles:
    - Connecting with exponential backoff
    - Hello/auth handshake
    - Sending support requests and waiting for acks
    - Retry logic for failed sends
    - Optional keepalive pings
    
    Example:
        client = WsClient()
        try:
            result = await client.send_support_request(payload)
            print(f"Support request created: {result}")
        finally:
            await client.aclose()
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the WebSocket client.
        
        Args:
            config: Configuration object. If None, uses default Config.
        """
        self.config = config or Config()
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._authenticated = False
        self._keepalive_task: Optional[asyncio.Task] = None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((
            ConnectionError,
            OSError,
            asyncio.TimeoutError,
            AuthenticationError,
        )),
        reraise=True,
    )
    async def connect(self) -> None:
        """
        Connect to the WebSocket server and perform hello/auth handshake.
        
        Uses exponential backoff with max 3 attempts.
        
        Raises:
            ConnectionError: If connection fails after retries.
            AuthenticationError: If authentication fails.
            AckTimeoutError: If hello_ack is not received in time.
        """
        if self.ws and self._authenticated:
            return  # Already connected
        
        logger.debug(f"Connecting to {self.config.WS_URL}")
        
        try:
            self.ws = await asyncio.wait_for(
                websockets.connect(self.config.WS_URL),
                timeout=self.config.CONNECT_TIMEOUT_SECONDS,
            )
        except (OSError, asyncio.TimeoutError) as e:
            logger.error(f"Failed to connect to {self.config.WS_URL}: {e}")
            raise ConnectionError(f"Failed to connect: {e}")
        
        # Send hello/auth
        hello = HelloMessage(token=self.config.IPC_TOKEN)
        await self.send_json(hello.model_dump())
        
        # Wait for hello_ack
        try:
            response = await self.recv_with_timeout(self.config.ACK_TIMEOUT_SECONDS)
            ack = HelloAck.model_validate(response)
            self._authenticated = True
            logger.info("Successfully authenticated with Flutter server")
            
            # Start keepalive if needed
            self._start_keepalive()
            
        except asyncio.TimeoutError:
            raise AckTimeoutError("Timeout waiting for hello_ack")
        except Exception as e:
            raise AuthenticationError(f"Authentication failed: {e}")
    
    async def send_json(self, data: Dict[str, Any]) -> None:
        """
        Send a JSON message to the server.
        
        Args:
            data: Dictionary to send as JSON.
        
        Raises:
            ConnectionError: If not connected.
        """
        if not self.ws:
            raise ConnectionError("Not connected to WebSocket server")
        
        message = json.dumps(data)
        logger.debug(f"Sending: {message}")
        await self.ws.send(message)
    
    async def recv_with_timeout(self, timeout: float) -> Dict[str, Any]:
        """
        Receive a JSON message with timeout.
        
        Args:
            timeout: Timeout in seconds.
        
        Returns:
            Parsed JSON message as a dictionary.
        
        Raises:
            asyncio.TimeoutError: If timeout is reached.
            ConnectionError: If not connected.
        """
        if not self.ws:
            raise ConnectionError("Not connected to WebSocket server")
        
        message = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
        logger.debug(f"Received: {message}")
        return json.loads(message)
    
    async def send_support_request(
        self, payload: SupportRequestPayload, max_retries: int = 2
    ) -> Dict[str, str]:
        """
        Send a support request and wait for acknowledgment.
        
        This method:
        1. Ensures connection (connects if needed)
        2. Sends the support request
        3. Waits for support_request_ack
        4. Retries on failure (max_retries times total)
        
        Args:
            payload: Support request payload.
            max_retries: Total number of attempts (default: 2).
        
        Returns:
            Dictionary with 'roomId' and 'requestId'.
        
        Raises:
            Various WsClientError subclasses on failure.
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Ensure we're connected and authenticated
                if not self._authenticated:
                    await self.connect()
                
                # Send the support request
                request = SupportRequest(payload=payload)
                await self.send_json(request.model_dump())
                
                # Wait for ack
                response = await self.recv_with_timeout(self.config.ACK_TIMEOUT_SECONDS)
                
                # Validate and parse ack
                ack = SupportRequestAck.model_validate(response)
                logger.info(
                    f"Support request acknowledged: roomId={ack.roomId}, "
                    f"requestId={ack.requestId}"
                )
                
                return {"roomId": ack.roomId, "requestId": ack.requestId}
            
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Support request attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                
                # Reset connection state for retry
                self._authenticated = False
                await self.aclose()
                
                if attempt < max_retries - 1:
                    # Wait before retry (exponential backoff)
                    await asyncio.sleep(2 ** attempt)
        
        # All retries exhausted
        logger.error(f"Failed to send support request after {max_retries} attempts")
        raise WsClientError(
            f"Failed after {max_retries} attempts. Last error: {last_error}"
        )
    
    def _start_keepalive(self) -> None:
        """Start keepalive ping task (every 25s)."""
        if self._keepalive_task and not self._keepalive_task.done():
            return
        
        async def keepalive_loop():
            try:
                while self.ws and not self.ws.closed:
                    await asyncio.sleep(25)
                    if self.ws and not self.ws.closed:
                        await self.ws.ping()
                        logger.debug("Sent keepalive ping")
            except Exception as e:
                logger.debug(f"Keepalive loop ended: {e}")
        
        self._keepalive_task = asyncio.create_task(keepalive_loop())
    
    async def aclose(self) -> None:
        """Close the WebSocket connection and cleanup."""
        # Cancel keepalive
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
        
        # Close connection
        if self.ws:
            try:
                await self.ws.close()
                logger.debug("WebSocket connection closed")
            except Exception as e:
                logger.debug(f"Error closing WebSocket: {e}")
        
        self._authenticated = False
        self.ws = None


# ============================================================================
# Convenience Functions
# ============================================================================

def create_meta(
    test_name: str,
    screenshot_b64: Optional[str] = None,
    trace_path: Optional[str] = None,
) -> Meta:
    """
    Create a Meta object with current timestamp.
    
    Args:
        test_name: Name/ID of the test.
        screenshot_b64: Optional base64-encoded screenshot.
        trace_path: Optional path to trace file.
    
    Returns:
        Meta object.
    """
    return Meta(
        testName=test_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
        screenshotB64=screenshot_b64,
        tracePath=trace_path,
    )

