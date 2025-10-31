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
    """Test script that opens Google and fails looking for phone field."""
    print("=" * 70)
    print("   GOOGLE.COM TEST - MiniAgent Hook Demonstration")
    print("=" * 70)
    print()
    print("This script will:")
    print("  • Open Google.com")
    print("  • Search for a phone number field (intentional failure)")
    print("  • Trigger the MiniAgent support request")
    print("  • Display completion banner")
    print()
    print("-" * 70)
    print()
    
    with sync_playwright() as p:
        # Launch browser (hook will inject debug port for Chromium)
        print("STEP 1: Launching Chromium browser...")
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        print("   ✓ Browser launched successfully")
        print()
        
        # Navigate to Google
        print("STEP 2: Navigating to Google.com...")
        page.goto("https://www.google.com")
        print(f"   ✓ Current URL: {page.url}")
        print(f"   ✓ Page Title: {page.title()}")
        print()
        
        time.sleep(1)
        
        # Purposely fail - search for phone number field
        print("STEP 3: Searching for phone number field...")
        print("   (This field doesn't exist - will trigger agent request)")
        try:
            # Try to find a phone number input field that doesn't exist
            page.fill("input[type='tel']", "+1234567890", timeout=5000)
            print("   ✓ Phone field found (unexpected!)")
        except Exception as e:
            print(f"   ✗ Error caught: {type(e).__name__}")
            print(f"   ✗ Message: {str(e)[:100]}...")
            print(f"   → MiniAgent support request sent automatically!")
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



