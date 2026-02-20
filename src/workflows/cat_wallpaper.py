
import time
import os
import sys
import argparse

# Ensure src is in path
sys.path.append(os.getcwd())

from src.actions import ActionEngine
from src.devtools_client import DevToolsClient

def main():
    # Parse Args
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=str, default="cat wallpaper", help="Search query for wallpaper")
    args = parser.parse_args()

    print(f"[*] Starting 'Wallpaper' Workflow (View Source Method)...")
    print(f"[*] Query: {args.query}")
    
    act = ActionEngine()
    
    # 1. Launch/Focus Firefox
    print("[1] Focusing Firefox...")
    try:
        act.focus_window("Firefox")
    except:
        print("    Launching Firefox...")
        act.launch_app("firefox")
        time.sleep(3)
    time.sleep(1)
    
    # 2. Search Google Images
    # standard lookup
    target_url = f"https://www.google.com/search?tbm=isch&q={args.query.replace(' ', '+')}"
    
    print(f"[2] Navigating to {target_url}...")
    act.hotkey(["ctrl", "l"])
    time.sleep(0.5)
    act.type_text(target_url)
    time.sleep(0.5)
    act.press_key("enter")
    
    # Wait for page load
    print("    Waiting for page load (5s)...")
    time.sleep(5)
    
    # 3. Open Source View (Ctrl+U) & Copy All
    print("[3] Scraping Page Source (Ctrl+U)...")
    act.hotkey(["ctrl", "u"])
    time.sleep(3) # Wait for new tab
    
    # Select All & Copy
    print("    Copying HTML...")
    act.hotkey(["ctrl", "a"])
    time.sleep(1)
    act.hotkey(["ctrl", "c"]) 
    time.sleep(1) # wait for clipboard
    
    # Close Source Tab (Clean up)
    act.hotkey(["ctrl", "w"])
    
    # 4. Parse Clipboard
    print("[4] Parsing HTML for images...")
    import pyperclip
    import re
    
    html_content = pyperclip.paste()
    if not html_content or len(html_content) < 100:
        print("[-] Clipboard empty or invalid.")
        return

    # Regex for Google Images thumbnails (usually encrypted-tbn0...) 
    # or generic http .jpg
    # We look for http pattern ending in jpg/png/jpeg inside quotes
    
    print(f"    Scanning {len(html_content)} bytes...")
    
    img_url = None
    
    # Strategy A: Google's specific thumbnail structure
    # They often look like: ["https://encrypted-tbn0.gstatic.com/images?q=...",
    # Let's find http...gstatic.com/images...
    
    patterns = [
        r'(https?://encrypted-tbn0\.gstatic\.com/images\?q=[^"]+)',
        r'(https?://[^"]+\.jpg)',
        r'(https?://[^"]+\.jpeg)',
        r'(https?://[^"]+\.png)'
    ]
    
    for p in patterns:
        matches = re.findall(p, html_content)
        if matches:
            # Filter out tiny ones if possible, but mostly just take the first meaningful one
            # Google source has many tiny icons. encrypted-tbn0 is the actual result thumb.
            for m in matches:
                if "gstatic.com" in m or len(m) > 50:
                    img_url = m
                    # Decode unicode escapes if any (google uses \u003d)
                    img_url = img_url.encode().decode('unicode-escape')
                    break
        if img_url: break
    
    if not img_url:
        print("[-] No image URL found in source.")
        return
        
    print(f"[+] Found URL: {img_url[:60]}...")
    
    # 5. Download Image
    save_path = os.path.abspath("cat_wallpaper_scraped.jpg")
    print(f"[5] Downloading to {save_path}...")
    if act.download_image(img_url, save_path):
        print("[+] Download success.")
        
        # 6. Set Wallpaper
        print("[6] Setting Wallpaper...")
        if act.set_wallpaper(save_path):
            print("[+] WALLPAPER SET SUCCESSFULLY! 🐱")
        else:
            print("[-] Failed to set wallpaper.")
    else:
        print("[-] Download failed.")

if __name__ == "__main__":
    main()
