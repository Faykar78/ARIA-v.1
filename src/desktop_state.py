
import time
import subprocess
import pyperclip
from src.actions import ActionEngine

class DesktopState:
    def __init__(self, action_engine=None):
        self.actor = action_engine if action_engine else ActionEngine()

    def get_active_window_title(self):
        """Delegates to ActionEngine's xdotool wrapper."""
        return self.actor.get_active_window()

    def get_browser_url(self):
        """
        Heuristic to get URL from active browser.
        1. Click Address Bar (Ctrl+L)
        2. Copy (Ctrl+C)
        3. Read Clipboard
        """
        # Preserving clipboard content could be nice, but for now we just overwrite.
        
        print("    [DesktopState] Attempting to extract URL...")
        
        # 1. Focus Address Bar
        self.actor.hotkey(["ctrl", "l"])
        time.sleep(0.2)
        
        # 2. Copy
        self.actor.hotkey(["ctrl", "c"])
        time.sleep(0.2)
        
        # 3. Read
        try:
            url = pyperclip.paste()
            # Basic validation
            if url and (url.startswith("http") or url.startswith("www") or "://" in url):
                return url.strip()
            return None
        except Exception as e:
            print(f"    [Error] Clipboard read failed: {e}")
            return None

    def get_context(self):
        """Returns a dict of current desktop state."""
        title = self.get_active_window_title()
        
        # Simple heuristic: if browser, try to get URL
        # We can expand this list (Firefox, Chrome, Brave, Edge)
        url = None
        browsers = ["Firefox", "Chrome", "Chromium", "Brave", "Edge"]
        is_browser = any(b.lower() in title.lower() for b in browsers)
        
        if is_browser:
             url = self.get_browser_url()
             
        return {
            "active_window": title,
            "is_browser": is_browser,
            "url": url,
            "timestamp": time.time()
        }
