#!/usr/bin/env python3
"""
Example Playwright script to demonstrate the MiniAgent hook.
This script intentionally has errors to trigger support requests.

NO MODIFICATIONS NEEDED - the hook intercepts errors automatically!
"""
from playwright.sync_api import sync_playwright
import time

def print_completion_banner():
    """Print a big ASCII art banner when script completes."""
    print("\n")
    print("=" * 80)
    print("=" * 80)
    print()
    print("   .-.-. .---. .---.   .-. .---.  .--.--. .-.   .-. .---.  .---. .-.  .-.")
    print("  { {-. }   { } }   )  | | } }  )  | {  } {} ) { } } }  )  { {__  {} ) | |")
    print("  .'-'} } {-. | |-.}   | | } |-'   } .  .} {__} { } |-'   } }   } {__} { |")
    print("  `---' `---' `-' `-'  `-' `-'     `----'`---'`-' `-'     `---' `---'`-'")
    print()
    print("                    .-.  .-. .---.  .---.                                ")
    print("                    {} )/ } } }  )  { {__                                ")
    print("                    } {__} { } |-'   } }                                 ")
    print("                    `---'`-' `-'     `---'                               ")
    print()
    print("  .---. .----. .-. .-. .---. .-.   .----. .---.  .----. .---. .-.   .-.")
    print("  } }   ) } }  {} )}  } } {-. } {}  ) } }  } {__  } }   } {_}} {} ) | |")
    print("  } |-.  |  }  } {__} { } '-' } {__} |  }  } }   } '-. } } } {__} { |")
    print("  `---'  `--'  `---'`-' `---' `---'  `--'  `---' `----' `---' `---'`-'")
    print()
    print("=" * 80)
    print("=" * 80)
    print("\n")

def google_search_test():
    """Test script that demonstrates when support requests are triggered."""
    print("=" * 70)
    print("   DUCKDUCKGO.COM TEST - NeedsAgentInterventionError Demo")
    print("=" * 70)
    print()
    print("This script will demonstrate two scenarios:")
    print("  1. Normal timeout (phone field) - NO support request")
    print("  2. Agent intervention needed - WILL send support request")
    print()
    print("-" * 70)
    print()
    
    with sync_playwright() as p:
        # Launch browser (hook will inject debug port for Chromium)
        print("STEP 1: Launching Chromium browser...")
        browser = p.chromium.launch(
            headless=False,
            slow_mo=500,
            args=[
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-background-timer-throttling",
            ],
        )
        page = browser.new_page()
        print("   ✓ Browser launched successfully")
        print()
        
        # Navigate to DuckDuckGo
        print("STEP 2: Navigating to DuckDuckGo...")
        page.goto("https://duckduckgo.com")
        print(f"   ✓ Current URL: {page.url}")
        print(f"   ✓ Page Title: {page.title()}")
        print()
        
        time.sleep(1)
        
        # SCENARIO 1: Normal timeout - NO support request
        print("SCENARIO 1: Looking for non-existent phone number field...")
        print("   (This will timeout but NOT trigger a support request)")
        try:
            page.fill("input[name='phone']", "555-1234", timeout=3000)
            print("   ✓ Phone field found!")
        except Exception as e:
            print(f"   ✗ Timeout: {type(e).__name__}")
            print(f"   ✓ NO support request sent (as expected)")
            print()
        
        time.sleep(2)
        
        # SCENARIO 2: Agent intervention needed - WILL trigger support request
        print("SCENARIO 2: Waiting for 'Agent Success' text (needs agent)...")
        print("   (This WILL trigger support request + hold)")
        print("   ACTION: Type 'Agent Success' in DuckDuckGo to help!")
        try:
            page.wait_for_selector("text=Agent Success", timeout=5000)
            print("   ✓ Found!")
        except Exception as e:
            print(f"   ✗ Timeout: {type(e).__name__}")
            print(f"   → Raising NeedsAgentInterventionError...")
            # Just raise it - the hook handles everything!
            raise NeedsAgentInterventionError(f"Need help finding 'Agent Success': {e}")
        
        time.sleep(2)
        print("STEP 3: Success! Cleaning up...")
        browser.close()
        print_completion_banner()

if __name__ == "__main__":
    google_search_test()
