#!/usr/bin/env python3
"""
Gemini Chat Workflow
Launches gemini.google.com, sends a prompt, and extracts the response using CDP.
"""

import subprocess
import time
import json
import argparse
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from pychrome import Browser
except ImportError:
    print("[!] pychrome not installed. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pychrome"], check=True)
    from pychrome import Browser


def launch_chrome_if_needed(url="https://gemini.google.com"):
    """Launch Chrome with CDP enabled if not already running."""
    profile_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../browser_data"))
    
    # Check if Chrome is already running with CDP
    try:
        browser = Browser(url="http://127.0.0.1:9222")
        tabs = browser.list_tab()
        print(f"[*] Chrome already running with {len(tabs)} tabs")
        return browser
    except:
        pass
    
    # Launch Chrome
    cmd = [
        "google-chrome",
        f"--user-data-dir={profile_path}",
        "--remote-debugging-port=9222",
        "--no-first-run",
        "--no-default-browser-check",
        url
    ]
    
    print(f"[*] Launching Chrome: {url}")
    subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait for Chrome to start with longer timeout
    print("[*] Waiting for Chrome to start...")
    time.sleep(5)  # Initial delay to let Chrome spawn
    
    for i in range(15):  # Increased retries
        try:
            time.sleep(2)
            browser = Browser(url="http://127.0.0.1:9222")
            tabs = browser.list_tab()
            if tabs:
                print(f"[+] Connected to Chrome with {len(tabs)} tabs")
                return browser
        except Exception as e:
            print(f"    Waiting for Chrome... ({i+1}/15)")
    
    raise Exception("Failed to connect to Chrome")


def navigate_to_gemini(tab):
    """Navigate to gemini.google.com if not already there."""
    # Get current URL
    result = tab.call_method("Runtime.evaluate", expression="window.location.href")
    current_url = result.get("result", {}).get("value", "")
    
    if "gemini.google.com" not in current_url:
        print("[*] Navigating to gemini.google.com...")
        tab.call_method("Page.navigate", url="https://gemini.google.com")
        time.sleep(3)


def send_prompt_to_gemini(tab, prompt):
    """Find the input field, type the prompt, and submit."""
    print(f"[*] Sending prompt: '{prompt}'")
    
    # Wait for page to load
    time.sleep(2)
    
    # Find input field - Gemini uses a contenteditable div or textarea
    # Try multiple selectors
    input_selectors = [
        "div[contenteditable='true']",
        "textarea[placeholder*='Enter']",
        "textarea",
        ".ql-editor",
        "[data-placeholder]",
        "div.ProseMirror",
    ]
    
    for selector in input_selectors:
        try:
            # Check if element exists
            check_script = f"""
            (function() {{
                const el = document.querySelector("{selector}");
                if (el) {{
                    el.focus();
                    return true;
                }}
                return false;
            }})()
            """
            result = tab.call_method("Runtime.evaluate", expression=check_script)
            if result.get("result", {}).get("value"):
                print(f"    Found input: {selector}")
                
                # Type the prompt
                type_script = f"""
                (function() {{
                    const el = document.querySelector("{selector}");
                    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {{
                        el.value = "{prompt}";
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }} else {{
                        el.innerText = "{prompt}";
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                    return true;
                }})()
                """
                tab.call_method("Runtime.evaluate", expression=type_script)
                time.sleep(0.5)
                
                # Find and click send button
                send_selectors = [
                    "button[aria-label*='Send']",
                    "button[aria-label*='submit']",
                    "button.send-button",
                    "button[data-test-id='send-button']",
                    "button[type='submit']",
                    "mat-icon[data-mat-icon-name='send']",
                    "button:has(mat-icon)",
                ]
                
                for send_sel in send_selectors:
                    send_script = f"""
                    (function() {{
                        const btn = document.querySelector("{send_sel}");
                        if (btn) {{
                            btn.click();
                            return true;
                        }}
                        return false;
                    }})()
                    """
                    result = tab.call_method("Runtime.evaluate", expression=send_script)
                    if result.get("result", {}).get("value"):
                        print(f"    Clicked send button: {send_sel}")
                        return True
                
                # If no send button found, try pressing Enter
                print("    No send button found, pressing Enter...")
                tab.call_method("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13)
                tab.call_method("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13)
                return True
                
        except Exception as e:
            continue
    
    print("[!] Could not find input field")
    return False


def wait_for_response(tab, timeout=60):
    """Wait for Gemini to finish generating response."""
    print("[*] Waiting for Gemini response...")
    
    start_time = time.time()
    last_text = ""
    stable_count = 0
    
    while time.time() - start_time < timeout:
        time.sleep(2)
        
        # Try to extract response text
        extract_script = """
        (function() {
            // Try multiple selectors for Gemini response
            const selectors = [
                '.model-response-text',
                '.response-content',
                '.markdown-main-panel',
                '[data-message-author="model"]',
                '.message-content',
                'model-response',
                '.response-container',
            ];
            
            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                if (els.length > 0) {
                    // Get the last response
                    const lastEl = els[els.length - 1];
                    return lastEl.innerText || lastEl.textContent;
                }
            }
            
            // Fallback: get all text from main content area
            const main = document.querySelector('main') || document.body;
            return main.innerText.substring(0, 5000);
        })()
        """
        
        result = tab.call_method("Runtime.evaluate", expression=extract_script)
        current_text = result.get("result", {}).get("value", "")
        
        # Check if response is stable (not still generating)
        if current_text and current_text == last_text:
            stable_count += 1
            if stable_count >= 2:  # Stable for 4 seconds
                print("[+] Response received!")
                return current_text
        else:
            stable_count = 0
            last_text = current_text
        
        # Check for loading indicator
        loading_script = """
        (function() {
            const loading = document.querySelector('.loading, .typing-indicator, [aria-busy="true"]');
            return loading !== null;
        })()
        """
        loading_result = tab.call_method("Runtime.evaluate", expression=loading_script)
        is_loading = loading_result.get("result", {}).get("value", False)
        
        if not is_loading and current_text:
            print("[+] Response received!")
            return current_text
    
    print("[!] Timeout waiting for response")
    return last_text


def extract_clean_response(raw_text):
    """Clean up the extracted response."""
    if not raw_text:
        return "No response received"
    
    # Remove common UI elements
    lines = raw_text.split('\n')
    clean_lines = []
    skip_patterns = ['Copy', 'Share', 'Good response', 'Bad response', 'Regenerate', 'Edit']
    
    for line in lines:
        line = line.strip()
        if line and not any(p in line for p in skip_patterns):
            clean_lines.append(line)
    
    return '\n'.join(clean_lines)


def chat_with_gemini(prompt):
    """Main function to chat with Gemini."""
    print("=" * 50)
    print("GEMINI CHAT WORKFLOW")
    print("=" * 50)
    
    # Launch Chrome
    browser = launch_chrome_if_needed()
    
    # Get or create tab
    tabs = browser.list_tab()
    if not tabs:
        raise Exception("No tabs available")
    
    tab = tabs[0]
    tab.start()
    tab.call_method("Page.enable")
    tab.call_method("Runtime.enable")
    # Note: Input.enable not needed for Runtime.evaluate based input
    
    # Navigate to Gemini
    navigate_to_gemini(tab)
    time.sleep(3)
    
    # Send prompt
    if not send_prompt_to_gemini(tab, prompt):
        tab.stop()
        return "Failed to send prompt"
    
    # Wait for response
    raw_response = wait_for_response(tab)
    
    # Clean and return
    clean_response = extract_clean_response(raw_response)
    
    tab.stop()
    
    print("\n" + "=" * 50)
    print("GEMINI RESPONSE:")
    print("=" * 50)
    print(clean_response)
    print("=" * 50)
    
    return clean_response


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chat with Gemini via browser")
    parser.add_argument("--prompt", "-p", type=str, default="How are you?",
                        help="The prompt to send to Gemini")
    args = parser.parse_args()
    
    response = chat_with_gemini(args.prompt)
    
    # Save response to file for the agent to read
    with open("gemini_response.txt", "w") as f:
        f.write(response)
    print(f"\n[*] Response saved to gemini_response.txt")
