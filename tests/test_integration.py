"""
Integration tests with in-process WebSocket server.

Validates:
- End-to-end hello + ack flow
- End-to-end support request + ack flow
- Full protocol compliance
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
)


@pytest.fixture
async def echo_server():
    """
    Create a full-featured mock server that implements the protocol.
    
    This server validates:
    - Hello message format
    - Token authentication
    - Support request format
    - Proper ack responses
    """
    received_messages = []
    
    async def handler(websocket):
        try:
            async for message in websocket:
                data = json.loads(message)
                received_messages.append(data)
                
                # Validate and handle hello
                if data.get("type") == "hello":
                    assert data.get("client") == "playwright-reporter"
                    assert data.get("version") == "1.0"
                    assert "token" in data
                    
                    if data.get("token") == "test-token":
                        await websocket.send(json.dumps({"type": "hello_ack"}))
                    else:
                        await websocket.send(
                            json.dumps({
                                "type": "error",
                                "message": "Invalid token"
                            })
                        )
                
                # Validate and handle support_request
                elif data.get("type") == "support_request":
                    assert "payload" in data
                    assert "description" in data["payload"]
                    assert "meta" in data["payload"]
                    assert "testName" in data["payload"]["meta"]
                    assert "timestamp" in data["payload"]["meta"]
                    
                    await websocket.send(
                        json.dumps({
                            "type": "support_request_ack",
                            "roomId": "integration-room-123",
                            "requestId": "integration-req-456",
                        })
                    )
        except websockets.exceptions.ConnectionClosed:
            pass
    
    # Start server
    server = await websockets.serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    
    yield f"ws://127.0.0.1:{port}/ws", received_messages
    
    # Cleanup
    server.close()
    await server.wait_closed()


@pytest.mark.asyncio
async def test_full_protocol_flow(echo_server):
    """Test complete protocol flow from hello to support request."""
    server_url, received_messages = echo_server
    
    # Setup config
    config = Config()
    config.WS_URL = server_url
    config.IPC_TOKEN = "test-token"
    
    # Create client and send support request
    client = WsClient(config)
    try:
        # Build payload
        meta = Meta(
            testName="integration_test",
            timestamp="2025-10-24T12:00:00Z",
        )
        payload = SupportRequestPayload(
            description="Integration test error",
            meta=meta,
        )
        
        # Send request (this will also handle connect + hello)
        result = await client.send_support_request(payload)
        
        # Verify response
        assert result["roomId"] == "integration-room-123"
        assert result["requestId"] == "integration-req-456"
        
        # Verify messages received by server
        assert len(received_messages) == 2
        
        # First message should be hello
        hello_msg = received_messages[0]
        assert hello_msg["type"] == "hello"
        assert hello_msg["token"] == "test-token"
        assert hello_msg["client"] == "playwright-reporter"
        
        # Second message should be support_request
        support_msg = received_messages[1]
        assert support_msg["type"] == "support_request"
        assert support_msg["payload"]["description"] == "Integration test error"
        assert support_msg["payload"]["meta"]["testName"] == "integration_test"
    
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_multiple_requests_same_connection(echo_server):
    """Test sending multiple support requests on the same connection."""
    server_url, received_messages = echo_server
    
    config = Config()
    config.WS_URL = server_url
    config.IPC_TOKEN = "test-token"
    
    client = WsClient(config)
    try:
        # Connect first
        await client.connect()
        
        # Send multiple requests
        for i in range(3):
            meta = Meta(
                testName=f"test_{i}",
                timestamp="2025-10-24T12:00:00Z",
            )
            payload = SupportRequestPayload(
                description=f"Error {i}",
                meta=meta,
            )
            
            result = await client.send_support_request(payload)
            assert result["roomId"] == "integration-room-123"
        
        # Should have received: 1 hello + 3 support requests
        assert len(received_messages) == 4
    
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_reconnect_after_disconnect(echo_server):
    """Test that client can reconnect after connection is lost."""
    server_url, received_messages = echo_server
    
    config = Config()
    config.WS_URL = server_url
    config.IPC_TOKEN = "test-token"
    
    client = WsClient(config)
    try:
        # First connection and request
        meta = Meta(testName="test_1", timestamp="2025-10-24T12:00:00Z")
        payload = SupportRequestPayload(description="First", meta=meta)
        result = await client.send_support_request(payload)
        assert result["roomId"] == "integration-room-123"
        
        # Simulate disconnect
        await client.aclose()
        
        # Second connection and request
        meta = Meta(testName="test_2", timestamp="2025-10-24T12:00:00Z")
        payload = SupportRequestPayload(description="Second", meta=meta)
        result = await client.send_support_request(payload)
        assert result["roomId"] == "integration-room-123"
        
        # Should have received: 2 hellos + 2 support requests
        assert len(received_messages) == 4
    
    finally:
        await client.aclose()

