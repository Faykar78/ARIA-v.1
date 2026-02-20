
import subprocess
import os
import sys
import argparse
import urllib.parse

def launch_browser(url="https://www.google.com"):
    """
    Launches Google Chrome as a detached process, sharing the same
    user_data_dir as the Playwright 'google_browser.py' tool.
    This ensures cookies (e.g. CAPTCHA solutions) are preserved.
    """
    # Path to browser_data (Same as google_browser.py)
    profile_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../browser_data"))
    
    # Construct command
    # Using Default profile inside browser_data
    # Note: Playwright might use a custom structure, but pointing Chrome to the same root usually works
    # or at least keeps it separated from system.
    cmd = [
        "google-chrome",
        f"--user-data-dir={profile_path}",
        "--remote-debugging-port=9222",  # Enable CDP for automation
        "--no-first-run",
        "--no-default-browser-check",
        url
    ]
    
    print(f"[*] Launching Chrome detached: {cmd}")
    print(f"[*] Profile: {profile_path}")
    
    # Detach process
    subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, default="https://www.google.com")
    parser.add_argument("--query", type=str, help="Search query to start with")
    args = parser.parse_args()
    
    target_url = args.url
    if args.query:
        target_url = f"https://www.google.com/search?q={urllib.parse.quote(args.query)}"
        
    launch_browser(target_url)
