
import os
import sys
import json
import pyautogui
# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from src.omni_client import OmniParserClient

class DebugView:
    def __init__(self):
        self.eyes = OmniParserClient()
        
    def analyze(self):
        # Capture
        print("[*] Capturing screen...")
        screen_path = "debug_screen.png"
        pyautogui.screenshot(screen_path)
        
        # Parse
        print("[*] Parsing with OmniParser...")
        labeled_img, detected_items = self.eyes.parse(screen_path)
        
        # Save labeled
        labeled_img.save("debug_labeled.png")
        print(f"[*] Saved debug_labeled.png")
        
        # Generate Brain Input (Same logic as brain.py)
        visible_elements = []
        for i, item in enumerate(detected_items[:60]):
            element = {
                "id": i,
                "type": item['label'],
            }
            text = item.get('text', '').strip()
            if text:
                if len(text) > 50: text = text[:47] + "..."
                element["text"] = text
            visible_elements.append(element)
            
        brain_input_str = json.dumps(visible_elements, indent=2)
        print("\n=== WHAT LLAMA SEES (Input String) ===")
        print(brain_input_str)
        
        # Full Raw Output
        with open("debug_omni_raw.json", "w") as f:
            json.dump(detected_items, f, indent=2)
        print("\n[*] Full raw output saved to debug_omni_raw.json")

if __name__ == "__main__":
    dbg = DebugView()
    dbg.analyze()
