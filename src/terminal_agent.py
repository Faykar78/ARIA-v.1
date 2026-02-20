import subprocess
import requests
import json
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from src.brain import LocalBrain as Brain

# This script gives Llama 3.1 DIRECT access to your shell via the Central Brain.
# It uses the custom 'aria' model we created.

print("[*] Starting Terminal Agent (Brain Pro Edition)...")
print("[*] WARNING: This agent has FULL SYSTEM ACCESS (rm, sudo, etc).")
print("[*] Actions Supported: Shell, WhatsApp (Bridge), Wallpaper, Python.\n")

brain = Brain()
history = []

while True:
    try:
        user_in = input("User@Brain:~$ ")
        if user_in.lower() in ['exit', 'quit']: break
        if not user_in.strip(): continue
        
        print("  [Brain] Thinking...")
        
        # 1. Ask Central Brain
        # We pass empty detected_items for text-only mode
        decision = brain.think(
            user_goal=user_in, 
            detected_items=[], 
            history=history, 
            active_window="Terminal",
            image_base64=None
        )
        
        # 2. Parse Decision
        action_type = decision.get("action")
        
        if action_type == "execute_whatsapp_js":
            code = decision.get("code", "")
            print(f"  [AI] Executing JS on WhatsApp: {code}")
            try:
                # Call workflow via subprocess to keep state clean or import directly?
                # Using subprocess matches main.py pattern
                proc = subprocess.run(
                    ["python3", "src/workflows/exec_whatsapp_js.py", "--js", code],
                    capture_output=True, text=True, check=True
                )
                print(f"  [Output]: {proc.stdout}")
                history.append(f"User: {user_in}\nAI Executed JS. Result: {proc.stdout}")
            except Exception as e:
                print(f"  [!] Failed: {e}")
                history.append(f"JS Failed: {e}")
                
        elif action_type == "send_whatsapp":
            contact = decision.get("contact")
            msg = decision.get("message")
            print(f"  [AI] Sending WhatsApp: '{msg}' -> '{contact}'")
            subprocess.run(["python3", "src/workflows/send_whatsapp.py", "--contact", contact, "--message", msg])
            history.append(f"Sent WhatsApp to {contact}")
            
        elif action_type == "read_whatsapp":
            print(f"  [AI] Reading WhatsApp messages...")
            proc = subprocess.run(["python3", "src/workflows/read_whatsapp.py"], capture_output=True, text=True)
            print(proc.stdout)
            history.append(f"Read WhatsApp: {proc.stdout}")

        # Native Shell Support
        elif action_type == "shell":
            cmd = decision.get("command")
            print(f"  [AI] Shell Command: {cmd}")
            # Security Warning?
            try:
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                output = proc.stdout + proc.stderr
                print(f"  [Output]:\n{output}")
                history.append(f"User: {user_in}\nRan Shell: {cmd}\nOutput: {output}")
            except Exception as e:
                print(f"  [!] Shell Error: {e}")
                history.append(f"Shell Failed: {e}")

        elif action_type == "run_code":
            script = decision.get("script")
            print(f"  [AI] Running Python Script:\n{script}")
            # Execute safely? No, full access.
            try:
                exec_globals = {}
                exec(script, exec_globals)
                history.append("Ran python script successfully.")
            except Exception as e:
                print(f"  [!] Script Error: {e}")

        else:
            print(f"  [AI] {decision}")
            history.append(f"AI Decision: {decision}")

    except KeyboardInterrupt:
        print("\nBye.")
        break
    except Exception as e:
        print(f"  [!] Error: {e}")

