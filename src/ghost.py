import time
import json
import os
import threading
from pynput import mouse, keyboard
from capture import ScreenCapture

# pip install pynput

OUTPUT_DIR = "training_data/ghost_logs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class GhostRecorder:
    def __init__(self):
        self.capturer = ScreenCapture()
        self.log = []
        self.start_time = time.time()
        self.episode_id = int(self.start_time)
        self.image_dir = os.path.join(OUTPUT_DIR, str(self.episode_id))
        os.makedirs(self.image_dir, exist_ok=True)
        
    def save_event(self, event_type, details):
        timestamp = time.time()
        
        # FIX: Re-initialize ScreenCapture here because pynput runs this in a new thread
        # and mss is not thread-safe if shared across threads on Linux (X11).
        local_capturer = ScreenCapture()
        
        img_filename = f"{int(timestamp*1000)}.jpg"
        img_path = os.path.join(self.image_dir, img_filename)
        
        # Save screenshot using thread-local instance
        local_capturer.save_screenshot(img_path)
        
        event = {
            "timestamp": timestamp,
            "type": event_type,
            "screenshot": img_path,
            "details": details
        }
        self.log.append(event)
        print(f"[Ghost] Recorded: {event_type} -> {details}")

        # Flush to disk periodically
        with open(os.path.join(self.image_dir, "log.jsonl"), "a") as f:
            f.write(json.dumps(event) + "\n")

    def start(self):
        print(f"[*] Ghost Recorder Started. ID: {self.episode_id}")
        print("[*] Press ESC to stop.")
        
        # Mouse Listener
        def on_click(x, y, button, pressed):
            if pressed:
                self.save_event("click", {"x": x, "y": y, "button": str(button)})

        # Keyboard Listener
        def on_press(key):
            try:
                k = key.char
            except:
                k = str(key)
                
            if k == 'Key.esc':
                return False # Stop listener
                
            # We record special keys or full typing sessions?
            # For now, simplistic singular key toggles
            self.save_event("keypress", {"key": k})

        # Non-blocking listeners
        m_listener = mouse.Listener(on_click=on_click)
        k_listener = keyboard.Listener(on_press=on_press)
        
        m_listener.start()
        k_listener.start()
        
        m_listener.join()
        k_listener.join()
        print("[*] Recording stopped.")

if __name__ == "__main__":
    ghost = GhostRecorder()
    ghost.start()
