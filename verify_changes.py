import sys
from unittest.mock import MagicMock

# Mock websocket module to avoid ImportError
sys.modules["websocket"] = MagicMock()

# Mock Playwright modules
sys.modules["playwright"] = MagicMock()
sys.modules["playwright.sync_api"] = MagicMock()
sys.modules["playwright.async_api"] = MagicMock()
sys.modules["playwright._impl"] = MagicMock()
sys.modules["playwright._impl._errors"] = MagicMock()

# Define exceptions
class PlaywrightError(Exception): pass
class TimeoutError(PlaywrightError): pass

sys.modules["playwright._impl._errors"].Error = PlaywrightError
sys.modules["playwright._impl._errors"].TimeoutError = TimeoutError

# Define Page class to be patched
class MockSyncPage:
    def click(self, selector):
        pass

# Assign to modules
sys.modules["playwright.sync_api"].Page = MockSyncPage
sys.modules["playwright.sync_api"].BrowserType = MagicMock()
sys.modules["playwright.async_api"].Page = MagicMock()
sys.modules["playwright.async_api"].BrowserType = MagicMock()

import os
import time
import threading
from unittest.mock import patch

# Set environment variables to enable the hook
os.environ["MINIAGENT_ENABLED"] = "1"
os.environ["MINIAGENT_TOKEN"] = "test_token"
os.environ["MINIAGENT_ON_ERROR"] = "report"

# Mock the websocket client to avoid actual connection attempts
with patch("miniagent_ws.MiniAgentWSClient") as MockClient:
    mock_ws_instance = MockClient.return_value
    
    # Import sitecustomize which triggers the hook
    import sitecustomize
    
    # Get the manager
    from miniagent_ws import get_support_manager
    manager = get_support_manager()
    
    # Mock the trigger_support_request method to verify calls
    manager.trigger_support_request = MagicMock()
    
    print("--- Test 1: NeedsAgentInterventionError (Global) ---")
    try:
        raise NeedsAgentInterventionError("Help me!")
    except NeedsAgentInterventionError:
        # Simulate unhandled exception by calling the hook manually
        # (since we are in a try/except block, sys.excepthook isn't called automatically)
        sitecustomize._handle_exception(NeedsAgentInterventionError, NeedsAgentInterventionError("Help me!"), None)
    
    if manager.trigger_support_request.called:
        print("PASS: Support request triggered for NeedsAgentInterventionError")
        print(f"Call args: {manager.trigger_support_request.call_args}")
    else:
        print("FAIL: Support request NOT triggered for NeedsAgentInterventionError")
    
    manager.trigger_support_request.reset_mock()
    
    print("\n--- Test 2: Normal Exception (Global) ---")
    try:
        raise ValueError("Just a normal error")
    except ValueError:
        sitecustomize._handle_exception(ValueError, ValueError("Just a normal error"), None)
        
    if manager.trigger_support_request.called:
        print("FAIL: Support request triggered for ValueError")
    else:
        print("PASS: Support request NOT triggered for ValueError")

    # Now let's test the Playwright wrapper
    print("\n--- Test 3: Playwright Wrapper (NeedsAgentInterventionError) ---")
    
    # The MockSyncPage.click should have been wrapped by sitecustomize
    page = MockSyncPage()
    
    # We need to inject the error into the method
    # Since sitecustomize wraps the original method, we can replace the original method on the class
    # BUT sitecustomize already replaced it with the wrapper.
    # The wrapper calls the original method.
    # So we need to make the ORIGINAL method raise the error.
    # But we defined the class before import.
    # The wrapper captured the original method.
    
    # Let's redefine the logic of the original method that was captured.
    # Wait, the wrapper calls `orig_method(self, *args, **kwargs)`.
    # `orig_method` is the function object.
    # We can't easily change it after wrapping unless we access the closure.
    
    # Alternative: We can mock the method on the instance if the wrapper calls self.method?
    # No, the wrapper IS the method.
    
    # Actually, we can just create a new class and manually wrap it using the logic from sitecustomize?
    # No, we can't access _wrap_method.
    
    # But wait, we defined `MockSyncPage.click` as `pass`.
    # The wrapper calls this `pass` function.
    # We want it to raise.
    # We should have defined it to raise based on some state, or use a mock side_effect.
    
    # Let's try to patch the `click` method on the class BEFORE import?
    # We did.
    
    # To make it raise different errors for different tests, we can use a side_effect on a shared mock?
    # But `MockSyncPage.click` is a plain function in my definition above.
    
    # Let's make `MockSyncPage.click` call a global mock.
    
    global_click_mock = MagicMock()
    
    def click_proxy(self, selector):
        global_click_mock(selector)
        
    MockSyncPage.click = click_proxy
    
    # Re-import sitecustomize to re-run interception (it checks _patched flag though)
    # We need to reset _patched flag?
    # sitecustomize._patched is global.
    
    # Actually, since we are running this script once, we should define the class properly before import.
    # But we already imported sitecustomize in the previous block?
    # No, the previous block was inside `with patch`.
    # But `sys.modules` cache persists.
    # `sitecustomize` is already imported.
    
    # We need to reload sitecustomize or reset it.
    if "sitecustomize" in sys.modules:
        del sys.modules["sitecustomize"]
    
    # Reset the _patched flag if we can access it? 
    # No, we deleted the module.
    
    # Re-import
    import sitecustomize
    
    # Now MockSyncPage.click is wrapped.
    
    # Test 3: NeedsAgentInterventionError
    global_click_mock.side_effect = NeedsAgentInterventionError("Click failed, need human")
    
    page = MockSyncPage()
    try:
        page.click("#btn")
    except NeedsAgentInterventionError:
        print("Caught expected error")
        
    if manager.trigger_support_request.called:
        print("PASS: Support request triggered for wrapped method")
        print(f"Call args: {manager.trigger_support_request.call_args}")
    else:
        print("FAIL: Support request NOT triggered for wrapped method")
        
    manager.trigger_support_request.reset_mock()
    
    print("\n--- Test 4: Playwright Wrapper (TimeoutError) ---")
    global_click_mock.side_effect = TimeoutError("Timeout!")
    
    try:
        page.click("#btn")
    except TimeoutError:
        print("Caught expected timeout")
        
    if manager.trigger_support_request.called:
        print("FAIL: Support request triggered for TimeoutError")
    else:
        print("PASS: Support request NOT triggered for TimeoutError")
