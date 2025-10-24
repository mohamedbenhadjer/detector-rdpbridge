"""
Tests for WebSocket client.

Validates:
- Connection and handshake
- Message sending/receiving
- Ack handling
- Error cases
"""

import asyncio
import json

import pytest
import websockets

from pw_ws_reporter.ws_client import (
    AckTimeoutError,
    AuthenticationError,
    Config,
    Meta,
    SupportRequestPayload,
    WsClient,
)


@pytest.fixture
def test_config():
    """Create a test configuration."""
    config = Config()
    config.IPC_TOKEN = "test-token"
    config.CONNECT_TIMEOUT_SECONDS = 2
    config.ACK_TIMEOUT_SECONDS = 2
    return config


@pytest.fixture
async def mock_server():
    """
    Create a mock WebSocket server for testing.
    
    This server:
    - Accepts connections
    - Responds to hello with hello_ack
    - Responds to support_request with support_request_ack
    """
    clients = []
    
    async def handler(websocket):
        clients.append(websocket)
        try:
            async for message in websocket:
                data = json.loads(message)
                
                # Handle hello
                if data.get("type") == "hello":
                    if data.get("token") == "test-token":
                        await websocket.send(json.dumps({"type": "hello_ack"}))
                    else:
                        await websocket.send(
                            json.dumps({"type": "error", "message": "Invalid token"})
                        )
                
                # Handle support_request
                elif data.get("type") == "support_request":
                    await websocket.send(
                        json.dumps({
                            "type": "support_request_ack",
                            "roomId": "test-room-123",
                            "requestId": "test-req-456",
                        })
                    )
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if websocket in clients:
                clients.remove(websocket)
    
    # Start server
    server = await websockets.serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    
    yield f"ws://127.0.0.1:{port}/ws"
    
    # Cleanup
    server.close()
    await server.wait_closed()


@pytest.mark.asyncio
async def test_connect_and_authenticate(mock_server, test_config):
    """Test successful connection and authentication."""
    test_config.WS_URL = mock_server
    
    client = WsClient(test_config)
    try:
        await client.connect()
        assert client._authenticated
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_connect_with_invalid_token(mock_server, test_config):
    """Test connection with invalid token fails authentication."""
    test_config.WS_URL = mock_server
    test_config.IPC_TOKEN = "wrong-token"
    
    client = WsClient(test_config)
    try:
        with pytest.raises((AuthenticationError, AckTimeoutError)):
            await client.connect()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_send_support_request(mock_server, test_config):
    """Test sending a support request and receiving ack."""
    test_config.WS_URL = mock_server
    
    # Build payload
    meta = Meta(testName="test", timestamp="2025-10-24T12:00:00Z")
    payload = SupportRequestPayload(
        description="Test error",
        meta=meta,
    )
    
    # Send request
    client = WsClient(test_config)
    try:
        result = await client.send_support_request(payload)
        
        assert result["roomId"] == "test-room-123"
        assert result["requestId"] == "test-req-456"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_send_json_without_connection(test_config):
    """Test that send_json fails if not connected."""
    client = WsClient(test_config)
    
    with pytest.raises(Exception):  # Should raise ConnectionError
        await client.send_json({"test": "data"})


@pytest.mark.asyncio
async def test_recv_with_timeout(mock_server, test_config):
    """Test receiving a message with timeout."""
    test_config.WS_URL = mock_server
    
    client = WsClient(test_config)
    try:
        await client.connect()
        
        # Send a message that will trigger a response
        meta = Meta(testName="test", timestamp="2025-10-24T12:00:00Z")
        payload = SupportRequestPayload(description="Test", meta=meta)
        
        from pw_ws_reporter.ws_client import SupportRequest
        request = SupportRequest(payload=payload)
        await client.send_json(request.model_dump())
        
        # Receive the ack
        response = await client.recv_with_timeout(2)
        assert response["type"] == "support_request_ack"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_aclose_idempotent(test_config):
    """Test that aclose can be called multiple times safely."""
    client = WsClient(test_config)
    
    # Should not raise even if never connected
    await client.aclose()
    await client.aclose()

