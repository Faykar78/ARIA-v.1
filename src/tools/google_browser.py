
from playwright.sync_api import sync_playwright
import urllib.parse
import time
import os

def search_google_browser(query, max_results=5):
    """
    Scrapes Google using a headless browser (Playwright) to bypass CAPTCHAs/Anti-Bot.
    Uses a persistent context to maintain cookies and trust.
    """
    print(f"[*] Browsing Google (Headless): '{query}'...")
    results = []
    
    # Store profile locally to save CAPTCHA passes/Cookies
    # Using absolute path for safety
    user_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../browser_data"))
    os.makedirs(user_data_dir, exist_ok=True)
    
    with sync_playwright() as p:
        # Launch persistent context
        # user_agent matches a real Chrome to avoid "HeadlessChrome" detection
        try:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir, # Positional arg, or correct kwarg is user_data_dir? 
                # Docs say: launch_persistent_context(user_data_dir, **kwargs)
                # So it's the first arg.
                headless=False,
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720},
                # Extra args to hide automation
                args=["--disable-blink-features=AutomationControlled"]
            )
        except Exception as e:
            return f"Browser Launch Error: {e}"
        
        try:
            page = browser.pages[0] if browser.pages else browser.new_page()
            
            # Go to Google
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            page.goto(url)
            
            # Handle Cookie Consent (common in EU/Headless)
            try:
                # "Accept all" button
                if page.get_by_role("button", name="Accept all").is_visible(timeout=2000):
                     page.get_by_role("button", name="Accept all").click()
                     time.sleep(1)
            except:
                pass
            
            # Wait for results or body
            try:
                # Wait for search box (implies page load)
                # Or wait for div.g directly
                page.wait_for_selector("#search", timeout=6000)
            except:
                print("    [!] Timeout waiting for results. Saving debug screenshot.")
                page.screenshot(path="google_error.png")
                # Dump text to see if it's CAPTCHA
                body_text = page.inner_text("body")
                if "unusual traffic" in body_text:
                    return "Google Blocked (CAPTCHA). Please run the browser visibly once to solve it."
                return f"Timeout. Body text: {body_text[:200]}"
            
            # Extract
            
            # 1. Featured Snippet / Time Widget / Calculator
            featured = page.query_selector("div.vk_c, div.xpdopen, div.cwUqwd, div.card-section")
            if featured:
                text = featured.inner_text().replace("\n", " ")
                results.append(f"0. [Featured Answer]: {text}")

            # Try multiple common result containers
            blocks = page.query_selector_all("div.g, div.tF2Cxc, div.MjjYud")
            if not blocks:
                # Fallback: Find any X that looks like a result
                blocks = page.query_selector_all("div.bvSTKc") # Another common one

            for g in blocks:
                title_el = g.query_selector("h3")
                link_el = g.query_selector("a")
                # Improved snippet selectors
                snippet_el = g.query_selector("div.VwiC3b, div.UB0dCd, div.s3v9rd, span.aCOpRe")

                if title_el and link_el:
                    title = title_el.inner_text()
                    link = link_el.get_attribute("href")
                    
                    if snippet_el:
                         snippet = snippet_el.inner_text()
                    else:
                         # Fallback: Capture the whole block text (first 200 chars)
                         snippet = g.inner_text().replace("\n", " ")[:200]
                    
                    results.append(f"{len(results)+1}. {title}: {snippet} ({link})")
                    
                if len(results) >= max_results:
                    break
            
            if not results:
                print("    [!] Debug: No results found. Saving 'google_debug.png' and 'google_debug.html'...")
                page.screenshot(path="google_debug.png")
                with open("google_debug.html", "w") as f:
                    f.write(page.content())
                    
        except Exception as e:
            return f"Browser Page Error: {e}"
        finally:
            # If visible, wait for user signal to close
            print("    [*] Browser visible. Press ENTER in terminal to close (or type a new command)...")
            try:
                user_input = input()
                if user_input.strip():
                    print(f"    [*] User command received: '{user_input}'")
                    results.append(f"\n[USER COMMAND]: {user_input}")
            except:
                pass

            # Close the context (variable name 'browser' is actually a context here)
            browser.close()
            
    return "\n".join(results) if results else "No results found."

def setup_google_browser_headed():
    """
    Launches a VISIBLE browser for the user to solve CAPTCHAs and save cookies.
    """
    print("[*] Launching VISIBLE browser for Google Setup...")
    print("    Please manually solve any CAPTCHAs or click 'Accept All' on the consent screen.")
    print("    Then type a search query to ensure it works.")
    print("    Close the browser window when done.")
    
    user_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../browser_data"))
    os.makedirs(user_data_dir, exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False, # VISIBLE
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://www.google.com")
        
        input("Press Enter here in the terminal once you have successfully searched on Google in the browser window...")
        
        browser.close()
        print("[*] Browser closed. Cookies/Context saved.")

if __name__ == "__main__":
    import sys
    if "--setup" in sys.argv:
        setup_google_browser_headed()
    else:
        print(search_google_browser("current time in india"))
