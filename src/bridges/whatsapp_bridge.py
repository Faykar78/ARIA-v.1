
from playwright.sync_api import sync_playwright
import time
import json

import subprocess
import os

class WhatsAppBridge:
    def __init__(self, cdp_port=9222):
        self.cdp_url = f"http://localhost:{cdp_port}"
        self.playwright = None
        self.browser = None
        self.page = None

    def connect(self):
        """Connect to the Chrome browser launched by main.py"""
        print(f"[*] [Bridge] Connecting to Chrome browser on {self.cdp_url}...")
        self.playwright = sync_playwright().start()
        
        try:
            self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url)
        except Exception as e:
            print(f"[-] [Bridge] Connection failed: {e}")
            print(f"[!] Make sure browser is running via 'open browser' or 'open whatsapp' first")
            return False

        try:
            # Find the WhatsApp Web page
            ctx = self.browser.contexts[0]
            # Look for web.whatsapp.com page
            whatsapp_page = None
            for p in ctx.pages:
                url = p.url
                print(f"    Found Page: '{p.title()}' - URL: {url}")
                if "web.whatsapp.com" in url:
                    whatsapp_page = p
                    break
            
            if not whatsapp_page:
                print(f"[-] [Bridge] WhatsApp Web page not found. Please open WhatsApp first.")
                return False
                
            self.page = whatsapp_page
            print(f"[+] [Bridge] Connected to WhatsApp Web!")
            return True
            
        except Exception as e:
            print(f"[-] [Bridge] Error finding WhatsApp page: {e}")
            return False

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def get_messages(self, limit=10):
        if not self.page: return None
        
        # Inject JS to scrape - Robust Version
        js_code = """
        (() => {
            const getText = (el) => el ? el.innerText.replace(/\\n/g, ' | ') : '';
            
            // Debug: Log to console which selectors work
            // Common selectors for WhatsApp Web (changes often)
            // 2024/2025: role="row" is used for chat list items in the left pane
            // The message list (conversation) also uses role="row" sometimes
            
            // Try identifying the Chat List
            const chatList = document.querySelectorAll('div[aria-label="Chat list"] [role="listitem"]');
            const chatListRows = document.querySelectorAll('div[aria-label="Chat list"] [role="row"]');
            
            let target = chatList.length > 0 ? chatList : chatListRows;
            
            // If still zero, try generic role="row" (might mix chats and messages)
            if (target.length === 0) {
                 target = document.querySelectorAll('[role="row"]');
            }
            
            console.log(`[Bridge] Found ${target.length} items`);
            
            return Array.from(target).slice(0, 20).map(row => {
                 return getText(row);
            });
        })()
        """
        try:
            result = self.page.evaluate(js_code)
            return result
        except Exception as e:
            print(f"    [!] JS Eval failed: {e}")
            return []

    def get_active_chat_messages(self):
        """Scrapes the currently open conversation."""
        if not self.page: return None
        js_code = """
        (() => {
            const getText = (el) => el ? el.innerText.replace(/\\n/g, ' ') : '';
            
            // Message container usually has role="application" or label "Message list"
            const msgList = document.querySelectorAll('div[aria-label="Message list"] [role="row"]');
            
            return Array.from(msgList).slice(-10).map(row => getText(row));
        })()
        """
        try:
            return self.page.evaluate(js_code)
        except:
            return []

    def highlight_element(self, selector):
        """Visual Debug: Highlight an element on the screen."""
        if not self.page: return
        self.page.evaluate(f"""
            document.querySelectorAll('{selector}').forEach(el => {{
                el.style.border = '2px solid red';
            }});
        """)

    def select_chat(self, contact_name):
        """
        Interacts with UI to search/select a chat.
        """
        if not self.page: return False
        print(f"    [Bridge] Selecting chat: {contact_name}")
        
        try:
            # Strategies for finding the search box
            # 1. 'Search' textbox by role
            # 2. Key shortcut Ctrl+/ (we can trigger via page.keyboard)
            
            # Using keyboard shortcut is often safest for focus
            self.page.keyboard.press("Control+Alt+/") # Common WA Web shortcut
            time.sleep(0.5)
            
            # Or click explicit selector (often changing classes)
            # .x1hx0egp is a class often used, but dangerous.
            # aria-label="Search" or "Search input textbox"
            
            # Let's try filling whatever is focused, or finding the box
            if self.page.get_by_role("textbox", name="Search").is_visible():
                self.page.get_by_role("textbox", name="Search").fill(contact_name)
            elif self.page.get_by_role("textbox", name="Search input textbox").is_visible():
                self.page.get_by_role("textbox", name="Search input textbox").fill(contact_name)
            else:
                 # Fallback: Just type, assuming focus is on search or we can Tab to it
                 print("    [Bridge] Search box not found, trying blind type...")
                 self.page.keyboard.press("Escape") # Clear context
                 self.page.keyboard.press("Control+Alt+/")
                 time.sleep(0.5)
                 self.page.keyboard.type(contact_name)
            
            time.sleep(1.5) # Wait for results
            self.page.keyboard.press("Enter") # Open first result
            time.sleep(1) 
            return True
            
        except Exception as e:
            print(f"    [!] Select chat failed: {e}")
            return False

    def send_message(self, text):
        if not self.page: return False
        print(f"    [Bridge] Sending: '{text}'")
        try:
            # Focus Main input
            # contenteditable in main region
            # Footer usually
            
            # Focus via Tab? Or finding contenteditable
            # Locator: footer contenteditable
            
            footer_input = self.page.locator('footer div[contenteditable="true"]')
            footer_input.click()
            footer_input.fill(text)
            self.page.keyboard.press("Enter")
            return True
        except Exception as e:
            print(f"    [!] Send failed: {e}")
            return False

    def send_file(self, file_path, caption=""):
        """Send a file (image, document, video) to the current chat."""
        if not self.page: return False
        
        import os
        if not os.path.exists(file_path):
            print(f"    [!] File not found: {file_path}")
            return False
        
        abs_path = os.path.abspath(file_path)
        print(f"    [Bridge] Sending file: '{abs_path}'")
        
        try:
            import time
            
            # Click the attach button (paperclip icon) - multiple selectors for different WA versions
            attach_selectors = [
                '[data-icon="plus"]',
                '[data-icon="attach-menu-plus"]', 
                '[title="Attach"]',
                '[aria-label="Attach"]',
                'button[title="Attach"]',
                'div[title="Attach"]',
                'span[data-icon="clip"]',
                '[data-testid="attach-menu-plus"]'
            ]
            
            attach_btn = None
            for selector in attach_selectors:
                try:
                    btn = self.page.locator(selector)
                    if btn.count() > 0:
                        attach_btn = btn.first
                        break
                except:
                    continue
            
            if not attach_btn:
                print("    [!] Could not find attach button")
                return False
                
            attach_btn.click()
            time.sleep(0.5)
            
            # Wait for menu and click document/photo option based on file type
            ext = os.path.splitext(file_path)[1].lower()
            
            # Set input file - WhatsApp uses a hidden file input
            # This selector works for the file input that appears
            file_input = self.page.locator('input[type="file"]').first
            file_input.set_input_files(abs_path)
            
            time.sleep(1)  # Wait for preview to load
            
            # Add caption if provided
            if caption:
                caption_input = self.page.locator('div[contenteditable="true"]').last
                caption_input.fill(caption)
            
            # Click send button
            send_btn = self.page.locator('[data-icon="send"], [aria-label="Send"]')
            send_btn.click()
            
            time.sleep(1)  # Wait for upload
            print(f"    [+] File sent successfully!")
            return True
            
        except Exception as e:
            print(f"    [!] Send file failed: {e}")
            return False

# Test function
if __name__ == "__main__":
    b = WhatsAppBridge()
    if b.connect():
        msgs = b.get_messages()
        print("MESSAGES:", msgs)
        # b.close() # Keep open?

