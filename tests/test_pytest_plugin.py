"""
Tests for pytest plugin.

Validates:
- Plugin auto-loads
- Failures are detected
- Support requests are sent
- Page fixture is extracted
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_page():
    """Create a mock Playwright Page object."""
    page = MagicMock()
    page.url = "https://example.com/test"
    page.title = MagicMock(return_value="Test Page")
    page.context.browser.browser_type.name = "chromium"
    return page


@pytest.fixture
def mock_ws_client():
    """Mock the WsClient to avoid actual network calls."""
    with patch("pw_ws_reporter.reporter.WsClient") as mock_client_class:
        mock_instance = AsyncMock()
        mock_instance.send_support_request = AsyncMock(
            return_value={"roomId": "mock-room", "requestId": "mock-req"}
        )
        mock_instance.aclose = AsyncMock()
        mock_client_class.return_value = mock_instance
        
        yield mock_client_class, mock_instance


def test_plugin_loads():
    """Test that the plugin can be imported."""
    from pw_ws_reporter import pytest_plugin
    
    assert hasattr(pytest_plugin, "pytest_configure")
    assert hasattr(pytest_plugin, "pytest_runtest_makereport")


@pytest.mark.asyncio
async def test_report_error_called_on_failure(mock_page, mock_ws_client):
    """Test that report_error is called when a test fails."""
    from pw_ws_reporter.reporter import report_error
    
    mock_client_class, mock_instance = mock_ws_client
    
    # Simulate a test failure
    try:
        raise ValueError("Test error")
    except ValueError as e:
        await report_error(
            exc=e,
            page=mock_page,
            test_name="test_example",
        )
    
    # Verify that send_support_request was called
    mock_instance.send_support_request.assert_called_once()
    
    # Verify the payload
    call_args = mock_instance.send_support_request.call_args
    payload = call_args[0][0]
    
    assert "Test error" in payload.description
    assert payload.meta.testName == "test_example"
    assert payload.controlTarget is not None
    assert payload.controlTarget.urlContains == "https://example.com/test"


@pytest.mark.asyncio
async def test_report_error_without_page(mock_ws_client):
    """Test that report_error works without a page object."""
    from pw_ws_reporter.reporter import report_error
    
    mock_client_class, mock_instance = mock_ws_client
    
    # Simulate a test failure without page
    try:
        raise RuntimeError("No page error")
    except RuntimeError as e:
        await report_error(
            exc=e,
            page=None,
            test_name="test_no_page",
        )
    
    # Verify that send_support_request was called
    mock_instance.send_support_request.assert_called_once()
    
    # Verify the payload has no controlTarget
    call_args = mock_instance.send_support_request.call_args
    payload = call_args[0][0]
    
    assert "No page error" in payload.description
    assert payload.controlTarget is None


@pytest.mark.asyncio
async def test_report_error_with_description_hint(mock_page, mock_ws_client):
    """Test that description_hint is included in the error message."""
    from pw_ws_reporter.reporter import report_error
    
    mock_client_class, mock_instance = mock_ws_client
    
    try:
        raise AssertionError("Assertion failed")
    except AssertionError as e:
        await report_error(
            exc=e,
            page=mock_page,
            description_hint="Login flow failed",
            test_name="test_login",
        )
    
    # Verify description includes hint
    call_args = mock_instance.send_support_request.call_args
    payload = call_args[0][0]
    
    assert "Login flow failed" in payload.description
    assert "Assertion failed" in payload.description

