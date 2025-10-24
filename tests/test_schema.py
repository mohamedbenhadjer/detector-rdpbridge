"""
Tests for Pydantic message schemas.

Validates:
- Schema validation
- Serialization/deserialization
- Required/optional fields
"""

import pytest
from pydantic import ValidationError

from pw_ws_reporter.ws_client import (
    ControlTarget,
    HelloAck,
    HelloMessage,
    Meta,
    SupportRequest,
    SupportRequestAck,
    SupportRequestPayload,
)


class TestHelloMessage:
    """Tests for HelloMessage schema."""
    
    def test_valid_hello_message(self):
        """Test creating a valid hello message."""
        msg = HelloMessage(token="test-token")
        
        assert msg.type == "hello"
        assert msg.token == "test-token"
        assert msg.client == "playwright-reporter"
        assert msg.version == "1.0"
    
    def test_hello_message_serialization(self):
        """Test serializing hello message to dict."""
        msg = HelloMessage(token="test-token")
        data = msg.model_dump()
        
        assert data == {
            "type": "hello",
            "token": "test-token",
            "client": "playwright-reporter",
            "version": "1.0",
        }
    
    def test_hello_message_requires_token(self):
        """Test that token is required."""
        with pytest.raises(ValidationError):
            HelloMessage()


class TestHelloAck:
    """Tests for HelloAck schema."""
    
    def test_valid_hello_ack(self):
        """Test parsing a valid hello ack."""
        ack = HelloAck(type="hello_ack")
        assert ack.type == "hello_ack"
    
    def test_hello_ack_from_dict(self):
        """Test deserializing hello ack from dict."""
        data = {"type": "hello_ack"}
        ack = HelloAck.model_validate(data)
        assert ack.type == "hello_ack"


class TestControlTarget:
    """Tests for ControlTarget schema."""
    
    def test_minimal_control_target(self):
        """Test creating control target with only required fields."""
        target = ControlTarget(browser="brave", debugPort=9222)
        
        assert target.browser == "brave"
        assert target.debugPort == 9222
        assert target.urlContains is None
        assert target.titleContains is None
        assert target.targetId is None
    
    def test_full_control_target(self):
        """Test creating control target with all fields."""
        target = ControlTarget(
            browser="chrome",
            debugPort=9223,
            urlContains="https://example.com",
            titleContains="Example Domain",
            targetId="target-123",
        )
        
        assert target.browser == "chrome"
        assert target.debugPort == 9223
        assert target.urlContains == "https://example.com"
        assert target.titleContains == "Example Domain"
        assert target.targetId == "target-123"
    
    def test_control_target_serialization(self):
        """Test serializing control target."""
        target = ControlTarget(
            browser="edge",
            debugPort=9222,
            urlContains="https://test.com",
        )
        data = target.model_dump()
        
        assert data["browser"] == "edge"
        assert data["debugPort"] == 9222
        assert data["urlContains"] == "https://test.com"
        assert data["titleContains"] is None


class TestMeta:
    """Tests for Meta schema."""
    
    def test_minimal_meta(self):
        """Test creating meta with only required fields."""
        meta = Meta(
            testName="test_login",
            timestamp="2025-10-24T12:00:00Z",
        )
        
        assert meta.testName == "test_login"
        assert meta.timestamp == "2025-10-24T12:00:00Z"
        assert meta.screenshotB64 is None
        assert meta.tracePath is None
    
    def test_full_meta(self):
        """Test creating meta with all fields."""
        meta = Meta(
            testName="test_checkout",
            timestamp="2025-10-24T13:00:00Z",
            screenshotB64="base64data",
            tracePath="/path/to/trace.zip",
        )
        
        assert meta.testName == "test_checkout"
        assert meta.screenshotB64 == "base64data"
        assert meta.tracePath == "/path/to/trace.zip"


class TestSupportRequest:
    """Tests for SupportRequest schema."""
    
    def test_minimal_support_request(self):
        """Test creating support request with minimal payload."""
        meta = Meta(testName="test", timestamp="2025-10-24T12:00:00Z")
        payload = SupportRequestPayload(description="Test error", meta=meta)
        request = SupportRequest(payload=payload)
        
        assert request.type == "support_request"
        assert request.payload.description == "Test error"
        assert request.payload.controlTarget is None
    
    def test_full_support_request(self):
        """Test creating support request with full payload."""
        target = ControlTarget(
            browser="brave",
            debugPort=9222,
            urlContains="https://example.com",
        )
        meta = Meta(testName="test", timestamp="2025-10-24T12:00:00Z")
        payload = SupportRequestPayload(
            description="Full test error",
            controlTarget=target,
            meta=meta,
        )
        request = SupportRequest(payload=payload)
        
        assert request.type == "support_request"
        assert request.payload.description == "Full test error"
        assert request.payload.controlTarget is not None
        assert request.payload.controlTarget.browser == "brave"
    
    def test_support_request_serialization(self):
        """Test serializing support request to dict."""
        meta = Meta(testName="test", timestamp="2025-10-24T12:00:00Z")
        payload = SupportRequestPayload(description="Error", meta=meta)
        request = SupportRequest(payload=payload)
        
        data = request.model_dump()
        
        assert data["type"] == "support_request"
        assert data["payload"]["description"] == "Error"
        assert data["payload"]["meta"]["testName"] == "test"


class TestSupportRequestAck:
    """Tests for SupportRequestAck schema."""
    
    def test_valid_support_request_ack(self):
        """Test parsing a valid support request ack."""
        data = {
            "type": "support_request_ack",
            "roomId": "room-123",
            "requestId": "req-456",
        }
        ack = SupportRequestAck.model_validate(data)
        
        assert ack.type == "support_request_ack"
        assert ack.roomId == "room-123"
        assert ack.requestId == "req-456"
    
    def test_support_request_ack_requires_ids(self):
        """Test that roomId and requestId are required."""
        with pytest.raises(ValidationError):
            SupportRequestAck(type="support_request_ack")

