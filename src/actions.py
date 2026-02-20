import pyautogui
import time
import random
import subprocess
import shutil

class ActionEngine:
    def __init__(self):
        # Fail-safe: moving mouse to corner will abort
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5 # Slower for reliability
        
        # Check for tools
        self.has_wmctrl = shutil.which("wmctrl") is not None
        self.has_xdotool = shutil.which("xdotool") is not None
        if not self.has_wmctrl or not self.has_xdotool:
            print("[WARN] xdotool or wmctrl not found. Window management features will be limited.")

    def move_to(self, x, y, duration=0.3):
        """Moves mouse to x,y smoothly."""
        pyautogui.moveTo(x, y, duration=duration)

    def get_mouse_pos(self):
        return pyautogui.position()

    def click(self, x, y):
        """Clicks at x,y."""
        self.move_to(x, y)
        pyautogui.click()
        
    def double_click(self, x, y):
        """Double clicks at x,y."""
        self.move_to(x, y)
        pyautogui.doubleClick()

    def type_text(self, text):
        """Types text."""
        pyautogui.write(text, interval=0.1)

    def press_key(self, key):
        """Presses a specific key (e.g. 'enter', 'esc')."""
        pyautogui.press(key)
        
    def hotkey(self, keys):
        """Presses a hotkey combination (e.g. ['ctrl', 't'])."""
        print(f"    [Action] Hotkey: {keys}")
        pyautogui.hotkey(*keys)

    def launch_app(self, app_name):
        """Launches an application in background."""
        print(f"    [Action] Launching: {app_name}")
        subprocess.Popen(app_name, shell=True)
        time.sleep(3) # Wait for launch

    def focus_window(self, title_part):
        """Focuses a window by title using wmctrl."""
        if self.has_wmctrl:
            print(f"    [Action] Focusing window: {title_part}")
            subprocess.run(["wmctrl", "-a", title_part])
            time.sleep(0.5)
        else:
            print("    [Error] wmctrl not installed.")

    def get_active_window(self):
        """Returns title of currently active window via xdotool."""
        if self.has_xdotool:
            try:
                # getactivewindow returns ID, getwindowname gets title
                wid = subprocess.check_output(["xdotool", "getactivewindow"], text=True).strip()
                title = subprocess.check_output(["xdotool", "getwindowname", wid], text=True).strip()
                return title
            except:
                return "Unknown"
        return "Unknown"

    def get_windows(self):
        """Returns list of open windows."""
        if self.has_wmctrl:
            try:
                out = subprocess.check_output(["wmctrl", "-l"], text=True)
                # Parse: 0x0123...  0 hostname  Window Title
                windows = []
                for line in out.strip().split("\n"):
                    parts = line.split(maxsplit=3)
                    if len(parts) >= 4:
                        windows.append(parts[3])
                return windows
            except:
                return []
        return []

    def set_wallpaper(self, image_path):
        """Sets GNOME wallpaper to the specified image path."""
        import os
        full_path = os.path.abspath(image_path)
        if not os.path.exists(full_path):
            print(f"    [Error] Image not found: {full_path}")
            return False
            
        uri = f"file://{full_path}"
        try:
            # Set for both light and dark modes in modern GNOME (Ubuntu Jammy+)
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri], check=False)
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri], check=False)
            print(f"    [Action] Wallpaper set to: {full_path}")
            return True
        except Exception as e:
            print(f"    [Error] Failed to set wallpaper: {e}")
            return False

    def download_image(self, url, save_path):
        """
        Downloads image from URL to save_path.
        Supports http/https and data:image/base64 URIs.
        """
        import requests
        import base64
        
        print(f"    [Action] Downloading image from {'data:...' if url.startswith('data:') else url}...")
        
        try:
            # 1. Handle Base64 Data URIs
            if url.startswith("data:image"):
                # format: data:image/jpeg;base64,/9j/4AAQSk...
                header, encoded = url.split(",", 1)
                data = base64.b64decode(encoded)
                with open(save_path, "wb") as f:
                    f.write(data)
                print(f"    [Action] Saved Base64 image to {save_path}")
                return True
                
            # 2. Handle Standard HTTP/HTTPS
            # Fake User-Agent to avoid 403s
            headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}
            res = requests.get(url, headers=headers, stream=True, timeout=10)
            if res.status_code == 200:
                with open(save_path, 'wb') as f:
                    for chunk in res.iter_content(1024):
                        f.write(chunk)
                print(f"    [Action] Saved to {save_path}")
                return True
            else:
                print(f"    [Error] Download failed with status: {res.status_code}")
                return False
        except Exception as e:
            print(f"    [Error] Download exception: {e}")
            return False

if __name__ == "__main__":
    act = ActionEngine()
    print("Action Engine Ready.")
    print("Windows:", act.get_windows())
