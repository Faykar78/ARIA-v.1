
import time
import sys
import os
sys.path.append(os.getcwd())

from src.desktop_state import DesktopState

def main():
    print("[*] Monitoring Desktop State for 10 seconds...")
    print("    PLEASE SWITCH TO A BROWSER WINDOW NOW.")
    
    state_reader = DesktopState()
    
    for i in range(10):
        try:
            state = state_reader.get_context()
            print(f"[{i}] Window: {state.get('active_window')} | Browser: {state.get('is_browser')}")
            if state.get('url'):
                print(f"    -> URL EXTRACTED: {state.get('url')}")
        except Exception as e:
            print(f"    Error: {e}")
            
        time.sleep(1)

if __name__ == "__main__":
    main()
