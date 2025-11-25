from playwright.sync_api import sync_playwright
import weakref

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    try:
        r = weakref.ref(page)
        print("Weakref supported!")
        print(f"Ref: {r}")
        print(f"Obj: {r()}")
    except TypeError as e:
        print(f"Weakref NOT supported: {e}")
    
    browser.close()
