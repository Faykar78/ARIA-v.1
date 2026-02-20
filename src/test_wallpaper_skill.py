
import os
import argparse
import sys
sys.path.append(os.getcwd())

from src.actions import ActionEngine

def main():
    act = ActionEngine()
    
    # 1. Create a dummy image (Blue color)
    import cv2
    import numpy as np
    dummy_path = os.path.abspath("test_wallpaper.png")
    
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    img[:] = (255, 100, 100) # Blue-ish (BGR)
    cv2.imwrite(dummy_path, img)
    print(f"[*] Created test wallpaper: {dummy_path}")
    
    # 2. Set Wallpaper
    print("[*] Setting wallpaper...")
    success = act.set_wallpaper(dummy_path)
    
    if success:
        print("[+] Wallpaper command executed successfully.")
        print("    Please check if your background changed to BLUE/PURPLE.")
    else:
        print("[-] Wallpaper command failed.")

if __name__ == "__main__":
    main()
