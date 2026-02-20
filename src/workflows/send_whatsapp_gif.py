#!/usr/bin/env python3
"""
Send a GIF via WhatsApp Web's built-in Tenor GIF search.

Automates the WhatsApp Web UI using xdotool:
  1. Focus WhatsApp window
  2. Search & click on the contact chat
  3. Open emoji panel → switch to GIF tab  
  4. Search for GIF query via Tenor
  5. Click first result → send

Usage:
  python3 send_whatsapp_gif.py --contact KRACK --query "happy cat"
"""

import subprocess
import time
import argparse
import sys
import os

def run_xdotool(*args):
    """Run xdotool command and return output."""
    cmd = ["xdotool"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    return result.stdout.strip()

def find_whatsapp_window():
    """Find WhatsApp Web window ID."""
    result = subprocess.run(
        ["xdotool", "search", "--name", "WhatsApp"],
        capture_output=True, text=True, timeout=5
    )
    windows = result.stdout.strip().split("\n")
    windows = [w for w in windows if w.strip()]
    
    if not windows:
        print("[-] No WhatsApp window found")
        return None
    
    # Prefer the main browser window (largest)
    for wid in windows:
        try:
            geo = subprocess.run(
                ["xdotool", "getwindowgeometry", wid],
                capture_output=True, text=True, timeout=2
            )
            if geo.returncode == 0:
                return wid
        except:
            continue
    
    return windows[0]

def focus_window(wid):
    """Focus and raise the WhatsApp window."""
    run_xdotool("windowactivate", "--sync", wid)
    run_xdotool("windowfocus", "--sync", wid)
    time.sleep(0.5)

def get_window_geometry(wid):
    """Get window position and size."""
    result = subprocess.run(
        ["xdotool", "getwindowgeometry", "--shell", wid],
        capture_output=True, text=True, timeout=2
    )
    geo = {}
    for line in result.stdout.strip().split("\n"):
        if "=" in line:
            key, val = line.split("=", 1)
            geo[key] = int(val)
    return geo

def click_relative(wid, x_pct, y_pct):
    """Click at a position relative to the window (as percentage of window size)."""
    geo = get_window_geometry(wid)
    if not geo:
        return False
    
    abs_x = geo.get("X", 0) + int(geo.get("WIDTH", 1000) * x_pct)
    abs_y = geo.get("Y", 0) + int(geo.get("HEIGHT", 800) * y_pct)
    
    run_xdotool("mousemove", "--sync", str(abs_x), str(abs_y))
    time.sleep(0.1)
    run_xdotool("click", "1")
    return True

def type_text(text, delay_ms=50):
    """Type text using xdotool."""
    # Use xdg clipboard approach for reliability (handles special chars)
    try:
        # Save current clipboard
        proc = subprocess.run(["xclip", "-selection", "clipboard", "-o"], 
                            capture_output=True, text=True, timeout=2)
        old_clipboard = proc.stdout
    except:
        old_clipboard = ""
    
    # Set clipboard to our text
    proc = subprocess.Popen(["xclip", "-selection", "clipboard"], 
                           stdin=subprocess.PIPE)
    proc.communicate(text.encode())
    
    # Paste with Ctrl+V
    time.sleep(0.1)
    run_xdotool("key", "ctrl+v")
    time.sleep(0.3)
    
    # Restore old clipboard
    try:
        proc = subprocess.Popen(["xclip", "-selection", "clipboard"],
                               stdin=subprocess.PIPE)
        proc.communicate(old_clipboard.encode())
    except:
        pass

def open_chat(wid, contact_name):
    """Open a chat by searching for the contact name."""
    geo = get_window_geometry(wid)
    if not geo:
        return False
    
    w = geo.get("WIDTH", 1000)
    h = geo.get("HEIGHT", 800)
    
    # Click on the search bar ("Search or start a new chat")
    # It's in the left sidebar, near the top
    search_x = geo["X"] + int(w * 0.22)
    search_y = geo["Y"] + int(h * 0.09)
    
    run_xdotool("mousemove", "--sync", str(search_x), str(search_y))
    time.sleep(0.1)
    run_xdotool("click", "1")
    time.sleep(0.5)
    
    # Type the contact name
    type_text(contact_name)
    time.sleep(1.5)  # Wait for search results
    
    # Click the first result (below the search bar)
    result_y = search_y + int(h * 0.15)
    run_xdotool("mousemove", "--sync", str(search_x), str(result_y))
    time.sleep(0.1)
    run_xdotool("click", "1")
    time.sleep(1.0)
    
    # Clear search by pressing Escape
    run_xdotool("key", "Escape")
    time.sleep(0.3)
    
    return True

def send_gif_via_picker(wid, query):
    """
    Automate the WhatsApp GIF picker:
    1. Click emoji button (smiley near message input)
    2. Click GIF tab
    3. Type search query
    4. Click first GIF result
    5. Click send button
    """
    geo = get_window_geometry(wid)
    if not geo:
        return False
    
    w = geo.get("WIDTH", 1000)
    h = geo.get("HEIGHT", 800)
    
    # Step 1: Click the emoji/smiley button
    # It's at the bottom-left of the chat area, left of the message input
    # Approximately at 38% X, 97% Y of the window
    emoji_x = geo["X"] + int(w * 0.40)
    emoji_y = geo["Y"] + int(h * 0.97)
    
    print(f"[*] Clicking emoji button at ({emoji_x}, {emoji_y})...")
    run_xdotool("mousemove", "--sync", str(emoji_x), str(emoji_y))
    time.sleep(0.1)
    run_xdotool("click", "1")
    time.sleep(0.8)
    
    # Step 2: Click the GIF tab
    # The GIF button is in the emoji panel tabs, typically bottom of the emoji panel
    # It's a text button labeled "GIF" — located roughly at 42% X, 92% Y
    gif_tab_x = geo["X"] + int(w * 0.42)
    gif_tab_y = geo["Y"] + int(h * 0.91)
    
    print(f"[*] Clicking GIF tab at ({gif_tab_x}, {gif_tab_y})...")
    run_xdotool("mousemove", "--sync", str(gif_tab_x), str(gif_tab_y))
    time.sleep(0.1)
    run_xdotool("click", "1")
    time.sleep(0.8)
    
    # Step 3: Click the search input ("Search GIFs via Tenor")
    # Located near the top of the GIF panel, roughly at 42% X, 35% Y
    search_x = geo["X"] + int(w * 0.55)
    search_y = geo["Y"] + int(h * 0.38)
    
    print(f"[*] Clicking GIF search at ({search_x}, {search_y})...")
    run_xdotool("mousemove", "--sync", str(search_x), str(search_y))
    time.sleep(0.1)
    run_xdotool("click", "1")
    time.sleep(0.5)
    
    # Step 4: Type the search query
    print(f"[*] Typing search query: '{query}'...")
    type_text(query)
    time.sleep(2.0)  # Wait for Tenor search results to load
    
    # Step 5: Click the first GIF result
    # GIF results grid starts below the search bar
    # First result is approximately at 42% X, 50% Y
    gif_result_x = geo["X"] + int(w * 0.50)
    gif_result_y = geo["Y"] + int(h * 0.55)
    
    print(f"[*] Clicking first GIF result at ({gif_result_x}, {gif_result_y})...")
    run_xdotool("mousemove", "--sync", str(gif_result_x), str(gif_result_y))
    time.sleep(0.1)
    run_xdotool("click", "1")
    time.sleep(1.5)  # Wait for preview to load
    
    # Step 6: Click the send button (green circle in bottom-right of preview)
    # The send button appears in the bottom-right area after selecting a GIF
    send_x = geo["X"] + int(w * 0.95)
    send_y = geo["Y"] + int(h * 0.95)
    
    print(f"[*] Clicking send button at ({send_x}, {send_y})...")
    run_xdotool("mousemove", "--sync", str(send_x), str(send_y))
    time.sleep(0.1)
    run_xdotool("click", "1")
    time.sleep(1.0)
    
    print(f"[+] GIF '{query}' sent!")
    return True

def main():
    parser = argparse.ArgumentParser(description="Send GIF via WhatsApp's Tenor picker")
    parser.add_argument("--contact", required=True, help="Contact/chat name")
    parser.add_argument("--query", required=True, help="GIF search term (e.g. 'happy cat')")
    args = parser.parse_args()
    
    print(f"[*] Sending GIF '{args.query}' to '{args.contact}' via WhatsApp GIF picker...")
    
    # Find WhatsApp window
    wid = find_whatsapp_window()
    if not wid:
        print("[-] WhatsApp Web window not found. Please open WhatsApp Web in your browser.")
        sys.exit(1)
    
    print(f"[+] Found WhatsApp window: {wid}")
    
    # Focus the window
    focus_window(wid)
    
    # Open the contact's chat
    print(f"[*] Opening chat with '{args.contact}'...")
    if not open_chat(wid, args.contact):
        print(f"[-] Failed to open chat with '{args.contact}'")
        sys.exit(1)
    
    # Wait for chat to fully load
    time.sleep(0.5)
    
    # Send the GIF via the picker
    if send_gif_via_picker(wid, args.query):
        print(f"\n[+] SUCCESS: GIF '{args.query}' sent to '{args.contact}'!")
    else:
        print(f"\n[-] FAILED: Could not send GIF")
        sys.exit(1)

if __name__ == "__main__":
    main()
