"""
Example of how to use the new NeedsAgentInterventionError.
This error is globally available when running with the detector-rdpbridge environment.
"""
from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            print("Navigating...")
            page.goto("https://example.com")
            
            # Example 1: Explicitly requesting agent help for logic you can't handle
            # raise NeedsAgentInterventionError("I don't know how to solve this captcha")
            
            # Example 2: Catching a timeout and escalating to agent
            try:
                print("Trying to click non-existent button...")
                page.click("#non-existent-button", timeout=2000)
            except Exception as e:
                # Decide if this error needs an agent
                print("Click failed, escalating to agent...")
                raise NeedsAgentInterventionError(f"Could not click button: {e}")
                
        except NeedsAgentInterventionError:
            # The sitecustomize hook will catch this and send the support request
            # You don't need to do anything here unless you want local logging
            print("Agent intervention requested!")
            raise
            
        browser.close()

if __name__ == "__main__":
    run()
