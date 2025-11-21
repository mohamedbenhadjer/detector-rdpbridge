#!/usr/bin/env python3
"""
Example Playwright script to demonstrate the MiniAgent hook.
This script intentionally has errors to trigger support requests.

NO MODIFICATIONS NEEDED - the hook intercepts errors automatically!

=== FOR HUMAN AGENTS ===
When this script fails, the RDP Host receives TWO critical pieces of info:
1. detection.successSelector - The EXACT element the Host watches for to detect success
   Example: "text=Agent Success"
2. description - Includes "| successSelector=..." so YOU know what to make appear

YOUR JOB as the agent:
- Read the error description to see what selector is needed
- Perform actions in the browser that make that selector appear on the page
- When the selector appears, the RDP Host will automatically mark the session as successful

Example: If successSelector="text=Agent Success"
→ Type "Agent Success" in Google's search bar and hit Enter
→ The text appears on the page → RDP Host detects success!
========================
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
    """Test script that opens Google and fails looking for phone field."""
    print("=" * 70)
    print("   GOOGLE.COM TEST - MiniAgent Hook Demonstration")
    print("=" * 70)
    print()
    print("This script will:")
    print("  • Open Google.com")
    print("  • Wait for 'Agent Success' (which isn't there yet)")
    print("  • Trigger the MiniAgent support request")
    print("  • YOU (the Agent) will search for 'Agent Success'")
    print("  • The script will detect success!")
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
        
        # Navigate to Google
        print("STEP 2: Navigating to Google.com...")
        page.goto("https://duckduckgo.com")
        print(f"   ✓ Current URL: {page.url}")
        print(f"   ✓ Page Title: {page.title()}")
        print()
        
        time.sleep(1)
        
        # Purposely fail - wait for "Agent Success" text
        print("STEP 3: Waiting for 'Agent Success' text...")
        print("   (This text doesn't exist yet - will trigger agent request)")
        print("   ACTION REQUIRED: When the browser opens, type 'Agent Success' in Google and search!")
        try:
            # Try to find text that isn't there yet
            # The Agent (you) must type this into the search bar to make it appear
            page.wait_for_selector("text=Agent Success", timeout=5000)
            print("   ✓ 'Agent Success' found! (Detection worked!)")
        except Exception as e:
            print(f"   ✗ Error caught: {type(e).__name__}")
            print(f"   ✗ Message: {str(e)[:100]}...")
            print(f"   → MiniAgent support request sent automatically!")
            print(f"   → RDP Host is now watching for: 'text=Agent Success'")
            print()
        
        time.sleep(2)
        
        # Show that browser is still running
        print("STEP 4: Verifying browser state...")
        print("   ✓ Browser is still running")
        print("   ✓ Page is still accessible")
        print(f"   ✓ Current URL: {page.url}")
        print()
        
        print("STEP 5: Cleaning up...")
        browser.close()
        print("   ✓ Browser closed")
        print()
        
        # Print big completion banner
        print_completion_banner()

if __name__ == "__main__":
    google_search_test()
