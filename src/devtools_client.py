
import subprocess
import time
import json
import pyperclip
import os
from src.actions import ActionEngine

class DevToolsClient:
    def __init__(self, action_engine=None):
        self.actor = action_engine if action_engine else ActionEngine()
        
    def inject_payload(self, js_code):
        """
        Injects JS code into the active window's DevTools console.
        Uses Clipboard Paste for speed and reliability.
        """
        # Minify logic: 
        # 1. Remove single line comments which break when newlines are removed
        lines = js_code.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            # Remove inline comments (naive check)
            if "//" in line:
                line = line.split("//")[0]
            cleaned_lines.append(line)
            
        minified_code = " ".join(cleaned_lines)
        
        # 1. Copy payload to clipboard
        pyperclip.copy(minified_code)
        time.sleep(0.1)
        
        # 2. [Firefox Bypass] Type "allow pasting" blindly 
        # Firefox blocks pastes until you type this. Chrome ignores it (usually).
        # We do it fast.
        self.actor.type_text("allow pasting")
        time.sleep(0.2)
        self.actor.press_key("enter")
        time.sleep(0.5)
        
        # Clear the "allow pasting" error/undefined from console if any
        # self.actor.hotkey(["ctrl", "l"]) # This clears console in some devtools, or use clear()
        
        # 3. Paste into console (Ctrl+V)
        print(f"    [DevTools] Pasting payload ({len(minified_code)} chars)...")
        self.actor.hotkey(["ctrl", "v"])
        time.sleep(0.5)
        
        # 4. Execute
        self.actor.press_key("enter")
        time.sleep(0.5) # Wait for JS execution
        
        return minified_code # Return what we injected for comparison checking

    def copy_dom_state(self):
        """
        Injects JS to copy the relevant DOM state to clipboard.
        """
        # Improved Payload for WhatsApp Web/Electron
        # Removed comments to avoid minification errors.
        # Uses DevTools copy() API.
        
        js_payload = """
        (function() {
            try {
                const getText = (el) => el ? el.innerText.replace(/\\n/g, ' | ') : '';
                
                let chatRows = Array.from(document.querySelectorAll('div[role="row"]'));
                if (chatRows.length === 0) {
                     chatRows = Array.from(document.querySelectorAll('div[role="listitem"]'));
                }
                if (chatRows.length === 0) {
                     chatRows = Array.from(document.querySelectorAll('div[tabindex="-1"]'));
                }
                
                const items = chatRows.map((row, idx) => {
                    return {
                        id: idx,
                        text: getText(row),
                        top: row.getBoundingClientRect().top,
                        height: row.getBoundingClientRect().height
                    };
                });
                
                const output = {
                    title: document.title,
                    item_count: items.length,
                    items: items,
                    timestamp: Date.now()
                };
                
                copy(JSON.stringify(output));
                console.log(">> AGENT: Copied " + items.length + " items <<");
            } catch (e) {
                console.error("AGENT_ERROR", e);
            }
        })();
        """
        return self.inject_payload(js_payload)
        
    def read_clipboard_json(self, previous_content=None, retries=10):
        """
        Reads the clipboard and attempts to parse JSON.
        Waits/Retries if content matches previous_content (race condition).
        """
        for i in range(retries):
            content = pyperclip.paste()
            
            # 1. Check if empty
            if not content:
                time.sleep(0.5)
                continue
                
            # 2. Check if identical to what we just injected (Wait for JS execution)
            if previous_content and content.strip() == previous_content.strip():
                if i % 2 == 0: print(f"    [DevTools] Waiting for clipboard updates ({i}/{retries})...")
                time.sleep(0.5)
                continue
                
            # 3. Try Parse
            try:
                # Cleaning: Sometimes clipboard has extra newlines or quotes
                clean_content = content.strip()
                if clean_content.startswith("'") or clean_content.startswith('"'):
                     # heuristic check if it's double encoded (sometimes copy() does this)
                     if clean_content.startswith('"') and clean_content.endswith('"'):
                         clean_content = clean_content[1:-1]
                     
                return json.loads(clean_content)
            except json.JSONDecodeError:
                if i == int(retries/2):
                     # If we are failing to parse, it might be double escaped or raw string
                     pass
                time.sleep(0.5)
            except Exception as e:
                print(f"[!] Clipboard read error: {e}")
                return None
                
        return None

    def refresh_state(self):
        """
        Full orchestration: 
        1. Inject Code
        2. Wait for clipboard to change from injected code -> JSON
        """
        print("[*] Injecting DOM extraction payload...")
        
        # Inject calls copy_dom_state which returns the minified code used
        minified = self.copy_dom_state()
        
        print("[*] Reading clipboard (waiting for JSON)...")
        state = self.read_clipboard_json(previous_content=minified)
        
        if state:
            print(f"[*] State captured. {len(state.get('items', []))} elements found.")
        else:
            print("[!] Failed to capture state via DevTools.")
            
        return state
