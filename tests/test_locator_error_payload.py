"""
Unit test: Locator error payload includes CDP criteria
Tests that Locator-originated errors include debugPort, urlContains, and titleContains.
"""
import sys
import os
from unittest.mock import MagicMock, patch
from playwright.sync_api import sync_playwright
import json

# Track captured payloads
captured_payloads = []

def mock_send_support_request(payload):
    """Mock implementation to capture support request payloads."""
    captured_payloads.append(payload)
    print(f"\n[CAPTURED] Support request payload:")
    print(json.dumps(payload, indent=2))

def test_locator_error_includes_cdp_criteria():
    """Test that Locator errors include debugPort, urlContains, and titleContains."""
    print("Starting Locator error payload test...")
    
    # Patch the WebSocket client's send_support_request method
    with patch('miniagent_ws.MiniAgentWSClient.send_support_request', side_effect=mock_send_support_request):
        with sync_playwright() as p:
            # Launch Chromium with debug port
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Navigate to a page
            page.goto("https://example.com")
            print(f"Navigated to: {page.url}")
            print(f"Page title: {page.title()}")
            
            # Test 1: Page method error (baseline)
            print("\n=== Test 1: Page.click error (baseline) ===")
            try:
                page.click("button:has-text('NonExistentButton')", timeout=1000)
            except Exception as e:
                print(f"✓ Caught expected Page error: {type(e).__name__}")
            
            # Test 2: Locator method error (the fix target)
            print("\n=== Test 2: Locator.click error (testing fix) ===")
            try:
                locator = page.locator("button:has-text('AnotherNonExistentButton')")
                locator.click(timeout=1000)
            except Exception as e:
                print(f"✓ Caught expected Locator error: {type(e).__name__}")
            
            browser.close()
    
    # Verify captured payloads
    print("\n=== Verification ===")
    assert len(captured_payloads) >= 2, f"Expected at least 2 payloads, got {len(captured_payloads)}"
    
    for i, payload in enumerate(captured_payloads):
        print(f"\nPayload {i+1}:")
        control_target = payload.get("controlTarget", {})
        
        # Check that all required fields are present
        has_debug_port = "debugPort" in control_target
        has_url = "urlContains" in control_target
        has_title = "titleContains" in control_target
        
        print(f"  - debugPort: {control_target.get('debugPort')} (present: {has_debug_port})")
        print(f"  - urlContains: {control_target.get('urlContains')} (present: {has_url})")
        print(f"  - titleContains: {control_target.get('titleContains')} (present: {has_title})")
        
        # Both Page and Locator errors should now include CDP criteria
        assert has_debug_port, f"Payload {i+1} missing debugPort"
        assert has_url, f"Payload {i+1} missing urlContains"
        assert has_title, f"Payload {i+1} missing titleContains"
        
        # Verify the values are correct
        assert control_target.get("debugPort") == 9222, f"Expected debugPort 9222, got {control_target.get('debugPort')}"
        assert "example.com" in control_target.get("urlContains", ""), "Expected example.com in URL"
        assert control_target.get("titleContains"), "Expected non-empty title"
    
    print("\n✓ All payloads include required CDP criteria")
    print("✓ Test completed successfully")
    return True

if __name__ == "__main__":
    # Import after patching is set up
    try:
        result = test_locator_error_includes_cdp_criteria()
        if result:
            print("\n" + "="*60)
            print("SUCCESS: Locator errors now include CDP criteria!")
            print("="*60)
            sys.exit(0)
        else:
            print("\n" + "="*60)
            print("FAILED: Test did not pass verification")
            print("="*60)
            sys.exit(1)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

