"""
Tests for retry and backoff logic.

Validates:
- Retry on connection failure
- Retry on send failure
- Exponential backoff
- Max retry limit
"""

import asyncio
import json

import pytest
import websockets

from pw_ws_reporter.ws_client import (
    Config,
    Meta,
    SupportRequestPayload,
    WsClient,
    WsClientError,
)


@pytest.fixture
def test_config():
    """Create a test configuration with short timeouts for testing."""
    config = Config()
    config.IPC_TOKEN = "test-token"
    config.CONNECT_TIMEOUT_SECONDS = 1
    config.ACK_TIMEOUT_SECONDS = 1
    return config


@pytest.fixture
async def flaky_server():
    """
    Create a mock server that fails the first attempt, then succeeds.
    
    This simulates network issues or server restarts.
    """
    attempt_count = {"hello": 0, "support_request": 0}
    
    async def handler(websocket):
        try:
            async for message in websocket:
                data = json.loads(message)
                
                # Handle hello - fail first attempt
                if data.get("type") == "hello":
                    attempt_count["hello"] += 1
                    if attempt_count["hello"] == 1:
                        # First attempt: close connection
                        await websocket.close()
                        return
                    else:
                        # Second attempt: succeed
                        await websocket.send(json.dumps({"type": "hello_ack"}))
                
                # Handle support_request - fail first attempt
                elif data.get("type") == "support_request":
                    attempt_count["support_request"] += 1
                    if attempt_count["support_request"] == 1:
                        # First attempt: no response (timeout)
                        await asyncio.sleep(2)
                    else:
                        # Second attempt: succeed
                        await websocket.send(
                            json.dumps({
                                "type": "support_request_ack",
                                "roomId": "retry-room",
                                "requestId": "retry-req",
                            })
                        )
        except websockets.exceptions.ConnectionClosed:
            pass
    
    # Start server
    server = await websockets.serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    
    yield f"ws://127.0.0.1:{port}/ws", attempt_count
    
    # Cleanup
    server.close()
    await server.wait_closed()


@pytest.mark.asyncio
async def test_retry_on_connection_failure(flaky_server, test_config):
    """Test that client retries connection on failure."""
    server_url, attempt_count = flaky_server
    test_config.WS_URL = server_url
    
    client = WsClient(test_config)
    try:
        # Should succeed after retry
        await client.connect()
        assert client._authenticated
        
        # Verify that it tried twice
        assert attempt_count["hello"] == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_retry_on_send_failure(flaky_server, test_config):
    """Test that send_support_request retries on failure."""
    server_url, attempt_count = flaky_server
    test_config.WS_URL = server_url
    
    # Build payload
    meta = Meta(testName="test", timestamp="2025-10-24T12:00:00Z")
    payload = SupportRequestPayload(description="Test retry", meta=meta)
    
    client = WsClient(test_config)
    try:
        # Should succeed after retry
        result = await client.send_support_request(payload, max_retries=2)
        
        assert result["roomId"] == "retry-room"
        assert result["requestId"] == "retry-req"
        
        # Verify that support_request was attempted twice
        # (hello might have been retried too)
        assert attempt_count["support_request"] >= 2
    finally:
        await client.aclose()


@pytest.fixture
async def always_failing_server():
    """Create a server that always fails to respond."""
    
    async def handler(websocket):
        try:
            async for message in websocket:
                # Never send any response
                pass
        except websockets.exceptions.ConnectionClosed:
            pass
    
    server = await websockets.serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    
    yield f"ws://127.0.0.1:{port}/ws"
    
    server.close()
    await server.wait_closed()


@pytest.mark.asyncio
async def test_max_retries_exhausted(always_failing_server, test_config):
    """Test that client raises error after exhausting retries."""
    test_config.WS_URL = always_failing_server
    
    # Build payload
    meta = Meta(testName="test", timestamp="2025-10-24T12:00:00Z")
    payload = SupportRequestPayload(description="Test fail", meta=meta)
    
    client = WsClient(test_config)
    try:
        # Should fail after max retries
        with pytest.raises(WsClientError):
            await client.send_support_request(payload, max_retries=2)
    finally:
        await client.aclose()

