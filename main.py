
import time
import argparse
import sys
import cv2
import base64
from src.capture import ScreenCapture
from src.detector import BaseDetector
from src.actions import ActionEngine
from src.brain import LocalBrain
from src.ears import Ears
from src.mouth import Mouth
from src.bridges.telegram_bridge import telegram_bridge
from src.bridges.email_bridge import email_bridge

def encode_image(image):
    """Encodes a CV2 image to base64 string."""
    _, buffer = cv2.imencode('.jpg', image)
    return base64.b64encode(buffer).decode('utf-8')

def main():
    parser = argparse.ArgumentParser(description="Local AI Desktop Agent")
    parser.add_argument("--goal", type=str, help="The goal for the agent (e.g., 'Open Terminal')", default=None)
    parser.add_argument("--vision_model", type=str, default="omni", help="Ollama Vision model")
    parser.add_argument("--action_model", type=str, default="qwen2.5vl:3b", help="Ollama Action/Reasoning model")
    parser.add_argument("--voice", action="store_true", help="Enable Voice Interaction (Jarvis Mode)")
    parser.add_argument("--train", action="store_true", help="Enable Interactive Training Mode")
    args = parser.parse_args()

    # 1. Initialize Components
    print("[*] Initializing Screen Capture...")
    cap = ScreenCapture()
    
    print(f"[*] Loading Detector (Vision Disabled/YOLO Removed)...")
    detector = BaseDetector()
    
    print(f"[*] Connecting to Brain (Ollama: {args.action_model})...")
    brain = LocalBrain(vision_model=args.vision_model, action_model=args.action_model)
    
    print("[*] Initializing Action Engine...")
    actor = ActionEngine()
    
    ears = None
    mouth = None
    if args.voice:
        print("[*] Initializing Voice Modules (Jarvis Mode)...")
        ears = Ears()
        mouth = Mouth()
        if mouth:
            mouth.speak("System initialized. Waiting for command.")

    # 4. Initialize Telegram Bridge (Async)
    # We do this in the background or lazily, but let's print status
    if telegram_bridge.token and telegram_bridge.token != "YOUR_TOKEN_HERE":
        print(f"[*] Telegram Bridge Configured (Token Found).")
    else:
        print(f"[*] Telegram Bridge: Token MISSING. Edit src/bridges/telegram_bridge.py to enable.")

    # 5. Initialize Email Bridge
    if not email_bridge._is_configured():
        print(f"[*] Email Bridge: Credentials MISSING. Edit src/bridges/email_bridge.py to enable.")
    else:
        print(f"[*] Email Bridge Configured.")

    user_goal = args.goal
    if not user_goal:
        if args.voice and ears:
            if mouth: mouth.speak("Please state your goal.")
            user_goal = ears.listen_once(timeout=5)
            if not user_goal:
                if mouth: mouth.speak("I didn't hear anything. Please type your goal.")
                print("[!] Voice timeout. Switching to text input.")
                user_goal = input("Enter your goal: ")
        else:
            user_goal = input("Enter your goal: ")

    print(f"[*] STARTING AGENT. Goal: '{user_goal}'")
    print("Press Ctrl+C to STOP/RESET the agent.")

    history = []
    last_message = ""  # For context memory (e.g., "send same text to X")

    # OUTER LOOP: Handles Resets (Ctrl+C)
    while True: 
        try:
            recent_actions = [] # Circuit breaker reset
            
            # Skip if goal is empty
            if not user_goal or not user_goal.strip():
                continue
            
            # INNER LOOP: Agent Steps
            while True:
                # --- REFLEX FAST PATH (Internal Feed) ---
                # Check for common commands that don't need vision
                reflex_decision = None
                goal_lower = user_goal.lower().strip()
                
                print(f"  [DEBUG] Checking reflex for: '{goal_lower}'")
                
                REFLEX_PATTERNS = {
                    "open browser": {"action": "browse", "url": "google.com", "reason": "Reflex: Opening Browser"},
                    "launch browser": {"action": "browse", "url": "google.com", "reason": "Reflex: Launching Browser"},
                    "open google": {"action": "browse", "url": "google.com", "reason": "Reflex: Opening Google"},
                    "open whatsapp": {"action": "browse", "url": "web.whatsapp.com", "reason": "Reflex: Opening WhatsApp Web"},
                    "read whatsapp": {"action": "browse", "url": "web.whatsapp.com", "reason": "Reflex: Opening WhatsApp Web"},
                    # AI Sites
                    "open use.ai": {"action": "browse", "url": "use.ai", "reason": "Reflex: Opening Use.AI"},
                    "open z.ai": {"action": "browse", "url": "z.ai", "reason": "Reflex: Opening Z.AI"},
                    "open gemini": {"action": "browse", "url": "gemini.google.com", "reason": "Reflex: Opening Gemini"},
                    "open claude": {"action": "browse", "url": "claude.ai", "reason": "Reflex: Opening Claude"},
                    "open chatgpt": {"action": "browse", "url": "chat.openai.com", "reason": "Reflex: Opening ChatGPT"},
                }
                
                # Exact match or "startswith" for speed
                for pattern, action in REFLEX_PATTERNS.items():
                    if goal_lower == pattern or goal_lower.startswith(pattern + " "):
                        print(f"[*] REFLEX TRIGGERED: '{pattern}' -> Skipping Vision.")
                        reflex_decision = action
                        break
                
                # LOGIN WORKFLOW REFLEX: Detect 'login/sign in to X' and browse to the site first
                if not reflex_decision:
                    import re
                    login_patterns = [
                        r'(?:login|sign\s*in)\s+(?:to\s+)?(\S+\.(?:ai|com|org|io|app))',
                        r'open\s+(\S+\.(?:ai|com|org|io|app))\s+(?:and\s+)?(?:login|sign\s*in)',
                        r'(?:go\s+to\s+)?(\S+\.(?:ai|com|org|io|app))\s+(?:and\s+)?(?:complete\s+)?(?:the\s+)?(?:login|sign\s*in)',
                    ]
                    for pattern in login_patterns:
                        match = re.search(pattern, goal_lower)
                        if match:
                            url = match.group(1).strip()
                            if not url.startswith("http"):
                                url = "https://" + url
                            print(f"[*] LOGIN REFLEX: Detected site '{url}' -> Browse first, then continue login flow.")
                            reflex_decision = {
                                "action": "browse",
                                "url": url,
                                "reason": f"Reflex: Login workflow - Opening {url}"
                            }
                            break
                
                # SHELL COMMAND REFLEX: Detect file/folder operations -> Skip OmniParser entirely
                if not reflex_decision:
                    import re
                    shell_patterns = [
                        # Create folder
                        (r'create\s+(?:a\s+)?folder\s+(?:named\s+)?(.+)', 'mkdir "{}"'),
                        (r'make\s+(?:a\s+)?(?:new\s+)?folder\s+(?:named\s+)?(.+)', 'mkdir "{}"'),
                        (r'mkdir\s+(.+)', 'mkdir "{}"'),
                        # Delete file/folder
                        (r'delete\s+(?:the\s+)?file\s+(.+)', 'rm "{}"'),
                        (r'remove\s+(?:the\s+)?file\s+(.+)', 'rm "{}"'),
                        (r'delete\s+(?:the\s+)?folder\s+(.+)', 'rmdir "{}"'),
                        (r'remove\s+(?:the\s+)?folder\s+(.+)', 'rmdir "{}"'),
                        # List files
                        (r'list\s+(?:all\s+)?files(?:\s+here)?', 'ls -la'),
                        (r'show\s+(?:all\s+)?files(?:\s+here)?', 'ls -la'),
                        (r'what\s+files\s+are\s+here', 'ls -la'),
                        (r'ls', 'ls -la'),
                        # Show current directory
                        (r'where\s+am\s+i', 'pwd'),
                        (r'current\s+directory', 'pwd'),
                        (r'pwd', 'pwd'),
                        # Disk usage
                        (r'disk\s+usage', 'df -h'),
                        (r'show\s+disk\s+space', 'df -h'),
                        # Move/Rename
                        (r'rename\s+(.+?)\s+to\s+(.+)', 'mv "{0}" "{1}"'),
                        (r'move\s+(.+?)\s+to\s+(.+)', 'mv "{0}" "{1}"'),
                    ]
                    
                    for pattern, cmd_template in shell_patterns:
                        match = re.search(pattern, goal_lower)
                        if match:
                            groups = match.groups()
                            if groups:
                                # Single capture group
                                if len(groups) == 1:
                                    command = cmd_template.format(groups[0].strip())
                                # Two capture groups (for rename/move)
                                elif len(groups) == 2:
                                    command = cmd_template.format(groups[0].strip(), groups[1].strip())
                            else:
                                command = cmd_template
                            
                            print(f"[*] SHELL REFLEX: '{goal_lower}' -> '{command}' (Skipping OmniParser)")
                            reflex_decision = {
                                "action": "shell",
                                "command": command,
                                "reason": "Reflex: Shell Command"
                            }
                            break
                
                # XDOTOOL/WMCTRL REFLEX: Window management commands with natural language variations
                if not reflex_decision:
                    import re
                    
                    # Keywords that suggest window/desktop operations (for quick filtering)
                    window_keywords = ["window", "minimize", "maximiz", "fullscreen", "desktop", "workspace", 
                                       "screen", "click", "type", "press", "key", "mouse", "scroll", "focus",
                                       "activate", "close", "kill", "resize", "move window", "raise", "bring",
                                       "switch", "hide", "show", "shrink", "expand", "tile", "snap", "lock"]
                    
                    if any(kw in goal_lower for kw in window_keywords):
                        xdotool_patterns = [
                            # === MINIMIZE WINDOW (many variations) ===
                            (r'minimize\s+(?:the\s+)?(?:current\s+)?(?:this\s+)?window', 'xdotool getactivewindow windowminimize'),
                            (r'minimize\s+this', 'xdotool getactivewindow windowminimize'),
                            (r'shrink\s+(?:the\s+)?window', 'xdotool getactivewindow windowminimize'),
                            (r'hide\s+(?:the\s+)?(?:current\s+)?window', 'xdotool getactivewindow windowminimize'),
                            (r'iconify', 'xdotool getactivewindow windowminimize'),
                            (r'put\s+(?:this\s+)?(?:window\s+)?in\s+(?:the\s+)?taskbar', 'xdotool getactivewindow windowminimize'),
                            
                            # === MAXIMIZE WINDOW ===
                            (r'maximize\s+(?:the\s+)?(?:current\s+)?(?:this\s+)?window', 'wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz'),
                            (r'maximize\s+this', 'wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz'),
                            (r'expand\s+(?:the\s+)?window', 'wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz'),
                            (r'make\s+(?:this\s+)?(?:window\s+)?(?:full\s+)?(?:size|big)', 'wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz'),
                            (r'unmaximize', 'wmctrl -r :ACTIVE: -b remove,maximized_vert,maximized_horz'),
                            (r'restore\s+window\s+size', 'wmctrl -r :ACTIVE: -b remove,maximized_vert,maximized_horz'),
                            
                            # === FULLSCREEN ===
                            (r'(?:make\s+)?(?:go\s+)?fullscreen', 'wmctrl -r :ACTIVE: -b toggle,fullscreen'),
                            (r'toggle\s+fullscreen', 'wmctrl -r :ACTIVE: -b toggle,fullscreen'),
                            (r'enter\s+fullscreen', 'wmctrl -r :ACTIVE: -b add,fullscreen'),
                            (r'exit\s+fullscreen', 'wmctrl -r :ACTIVE: -b remove,fullscreen'),
                            (r'full\s+screen\s+mode', 'wmctrl -r :ACTIVE: -b toggle,fullscreen'),
                            
                            # === CLOSE/KILL WINDOW ===
                            (r'close\s+(?:the\s+)?(?:this\s+)?(?:current\s+)?window', 'xdotool getactivewindow windowclose'),
                            (r'close\s+this', 'xdotool getactivewindow windowclose'),
                            (r'kill\s+(?:the\s+)?(?:this\s+)?window', 'xdotool getactivewindow windowkill'),
                            (r'force\s+close', 'xdotool getactivewindow windowkill'),
                            (r'terminate\s+(?:this\s+)?(?:app|application|window)', 'xdotool getactivewindow windowkill'),
                            
                            # === FOCUS/ACTIVATE WINDOW ===
                            (r'focus\s+(?:on\s+)?(.+?)(?:\s+window)?$', 'xdotool search --name "{}" windowactivate'),
                            (r'activate\s+(.+?)(?:\s+window)?$', 'xdotool search --name "{}" windowactivate'),
                            (r'switch\s+to\s+(.+?)(?:\s+window)?$', 'xdotool search --name "{}" windowactivate'),
                            (r'bring\s+(.+?)\s+to\s+(?:front|focus)', 'xdotool search --name "{}" windowactivate'),
                            (r'go\s+to\s+(.+?)(?:\s+window)?$', 'xdotool search --name "{}" windowactivate'),
                            
                            # === RAISE WINDOW ===
                            (r'raise\s+(?:the\s+)?(.+?)(?:\s+window)?$', 'xdotool search --name "{}" windowraise'),
                            (r'bring\s+(.+?)\s+(?:to\s+)?top', 'xdotool search --name "{}" windowraise'),
                            
                            # === DESKTOP/WORKSPACE SWITCHING ===
                            (r'(?:switch|go)\s+to\s+(?:desktop|workspace)\s+(\d+)', 'wmctrl -s {}'),
                            (r'(?:go\s+to\s+)?desktop\s+(\d+)', 'wmctrl -s {}'),
                            (r'(?:go\s+to\s+)?workspace\s+(\d+)', 'wmctrl -s {}'),
                            (r'next\s+(?:desktop|workspace)', 'xdotool key super+Right'),
                            (r'previous\s+(?:desktop|workspace)', 'xdotool key super+Left'),
                            
                            # === MOVE WINDOW TO DESKTOP ===
                            (r'move\s+(?:this\s+)?(?:window\s+)?to\s+(?:desktop|workspace)\s+(\d+)', 'wmctrl -r :ACTIVE: -t {}'),
                            (r'send\s+(?:this\s+)?(?:window\s+)?to\s+(?:desktop|workspace)\s+(\d+)', 'wmctrl -r :ACTIVE: -t {}'),
                            
                            # === ALWAYS ON TOP / STICKY ===
                            (r'(?:make\s+)?(?:window\s+)?always\s+on\s+top', 'wmctrl -r :ACTIVE: -b add,above'),
                            (r'pin\s+(?:this\s+)?(?:window\s+)?(?:to\s+)?(?:all\s+)?(?:desktops)?', 'wmctrl -r :ACTIVE: -b add,sticky'),
                            (r'stick(?:y)?\s+window', 'wmctrl -r :ACTIVE: -b add,sticky'),
                            
                            # === KEYBOARD SHORTCUTS ===
                            (r'press\s+(.+)', 'xdotool key {}'),
                            (r'hit\s+(.+)\s+key', 'xdotool key {}'),
                            (r'type\s+(.+)', 'xdotool type "{}"'),
                            (r'press\s+alt\s*\+?\s*tab', 'xdotool key alt+Tab'),
                            (r'switch\s+windows', 'xdotool key alt+Tab'),
                            (r'lock\s+(?:the\s+)?screen', 'xdotool key super+l'),
                            (r'take\s+(?:a\s+)?screenshot', 'xdotool key Print'),
                            (r'screenshot', 'xdotool key Print'),
                            (r'open\s+(?:the\s+)?activities', 'xdotool key super'),
                            (r'show\s+(?:the\s+)?overview', 'xdotool key super'),
                            
                            # === MOUSE ===
                            (r'click\s+at\s+(\d+)\s*,?\s*(\d+)', 'xdotool mousemove {} {} click 1'),
                            (r'right\s+click', 'xdotool click 3'),
                            (r'double\s+click', 'xdotool click --repeat 2 1'),
                            (r'scroll\s+(?:down|lower)', 'xdotool click 5'),
                            (r'scroll\s+(?:up|higher)', 'xdotool click 4'),
                            (r'(?:get\s+)?mouse\s+(?:position|location)', 'xdotool getmouselocation'),
                            
                            # === WINDOW INFO ===
                            (r'list\s+(?:all\s+)?(?:open\s+)?windows', 'wmctrl -l'),
                            (r'show\s+(?:all\s+)?(?:open\s+)?windows', 'wmctrl -l'),
                            (r'what\s+windows\s+are\s+open', 'wmctrl -l'),
                            (r'(?:show\s+)?(?:all\s+)?desktops', 'wmctrl -d'),
                            (r'(?:get\s+)?current\s+desktop', 'xdotool get_desktop'),
                            (r'which\s+desktop\s+am\s+i\s+on', 'xdotool get_desktop'),
                        ]
                        
                        for pattern, cmd_template in xdotool_patterns:
                            match = re.search(pattern, goal_lower)
                            if match:
                                groups = match.groups()
                                if groups:
                                    # Handle numeric args (desktop numbers need -1 for 0-indexed)
                                    if len(groups) == 1:
                                        arg = groups[0].strip()
                                        # Desktop numbers: adjust if needed
                                        if 'wmctrl -s' in cmd_template or '-t' in cmd_template:
                                            try:
                                                arg = str(int(arg) - 1)  # Convert to 0-indexed
                                            except:
                                                pass
                                        command = cmd_template.format(arg)
                                    elif len(groups) == 2:
                                        command = cmd_template.format(groups[0].strip(), groups[1].strip())
                                else:
                                    command = cmd_template
                                
                                print(f"[*] XDOTOOL REFLEX: '{goal_lower}' -> '{command}' (Skipping OmniParser)")
                                reflex_decision = {
                                    "action": "shell",
                                    "command": command,
                                    "reason": "Reflex: X11 Window Command"
                                }
                                break
                if not reflex_decision and "whatsapp" in goal_lower and "send" in goal_lower and "file" not in goal_lower:
                    import re
                    # Pattern: send <message> to <contact> on whatsapp
                    match = re.search(r'send\s+(.+?)\s+to\s+(.+?)\s+on\s+whatsapp', goal_lower)
                    if match:
                        message = match.group(1).strip()
                        contact = match.group(2).strip()
                        
                        # Resolve context references like "same text", "it", "that"
                        context_words = ["the same text", "same text", "the same", "same message", "it", "that"]
                        if message in context_words and last_message:
                            print(f"[*] WHATSAPP REFLEX: Resolved '{message}' to '{last_message}'")
                            message = last_message
                        
                        # EMOJI SUPPORT: Convert emoji names to Unicode
                        EMOJI_MAP = {
                            # Faces
                            ":smile:": "😊", ":laugh:": "😂", ":joy:": "😂", ":lol:": "🤣",
                            ":wink:": "😉", ":heart_eyes:": "😍", ":love:": "❤️", ":heart:": "❤️",
                            ":cry:": "😢", ":sad:": "😢", ":angry:": "😠", ":cool:": "😎",
                            ":thinking:": "🤔", ":confused:": "😕", ":surprised:": "😮", ":shocked:": "😱",
                            # Gestures
                            ":thumbsup:": "👍", ":thumbs_up:": "👍", ":ok:": "👌", ":clap:": "👏",
                            ":wave:": "👋", ":pray:": "🙏", ":muscle:": "💪", ":fire:": "🔥",
                            ":100:": "💯", ":party:": "🎉", ":celebrate:": "🎊",
                            # Objects
                            ":star:": "⭐", ":check:": "✅", ":x:": "❌", ":warning:": "⚠️",
                            ":bell:": "🔔", ":phone:": "📱", ":email:": "📧", ":money:": "💰",
                            # Nature
                            ":sun:": "☀️", ":moon:": "🌙", ":rainbow:": "🌈", ":flower:": "🌸",
                        }
                        
                        for emoji_name, emoji_char in EMOJI_MAP.items():
                            message = message.replace(emoji_name, emoji_char)
                        
                        # Also support natural language emojis (without colons)
                        NATURAL_EMOJI = {
                            "thumbs up": "👍", "thumbsup": "👍", "smiley": "😊", "heart": "❤️",
                            "fire": "🔥", "100": "💯", "party": "🎉", "clap": "👏",
                        }
                        for word, emoji_char in NATURAL_EMOJI.items():
                            if message == word:
                                message = emoji_char
                                break
                        
                        # Store for future reference
                        last_message = message
                        
                        print(f"[*] WHATSAPP REFLEX: Sending '{message}' to '{contact}' -> Skipping Vision.")
                        reflex_decision = {
                            "action": "send_message",
                            "message": message,
                            "recipient": contact,
                            "reason": "Reflex: WhatsApp Send"
                        }
                
                # WHATSAPP FILE SEND REFLEX: "send file X to Y on whatsapp" or "send the file X to Y"
                if not reflex_decision and "whatsapp" in goal_lower and "send" in goal_lower and "file" in goal_lower:
                    import re
                    # Pattern: send (the)? file <path> to <contact> on whatsapp
                    match = re.search(r'send\s+(?:the\s+)?(?:a\s+)?file\s+(.+?)\s+to\s+(.+?)\s+on\s+whatsapp', goal_lower)
                    if match:
                        file_path = match.group(1).strip()
                        contact = match.group(2).strip()
                        
                        import os
                        import subprocess
                        
                        # Expand ~ to home directory
                        if file_path.startswith('~'):
                            file_path = os.path.expanduser(file_path)
                        
                        # If not a valid FILE (not folder), SEARCH for it
                        if not os.path.isfile(file_path):
                            print(f"[*] '{file_path}' is not a file, searching...")
                            
                            # Search in common locations with 'find' command
                            search_dirs = [
                                os.path.expanduser("~/Downloads"),
                                os.path.expanduser("~/Documents"),
                                os.path.expanduser("~/Pictures"),
                                os.path.expanduser("~/Desktop"),
                                os.path.expanduser("~"),
                            ]
                            
                            found_file = None
                            for search_dir in search_dirs:
                                if os.path.exists(search_dir):
                                    try:
                                        result = subprocess.run(
                                            ["find", search_dir, "-maxdepth", "3", "-iname", f"*{file_path}*", "-type", "f"],
                                            capture_output=True, text=True, timeout=5
                                        )
                                        if result.stdout.strip():
                                            # Take first match
                                            found_file = result.stdout.strip().split('\n')[0]
                                            print(f"[*] Found: {found_file}")
                                            break
                                    except:
                                        pass
                            
                            if found_file:
                                file_path = found_file
                            else:
                                print(f"[!] Could not find file matching '{match.group(1)}'")
                        
                        print(f"[*] WHATSAPP FILE REFLEX: Sending file '{file_path}' to '{contact}' -> Skipping Vision.")
                        reflex_decision = {
                            "action": "send_file",
                            "file_path": file_path,
                            "recipient": contact,
                            "reason": "Reflex: WhatsApp File Send"
                        }
                
                # SEND "THIS" FILE REFLEX: "send this to Y on whatsapp" (uses selected file from file manager)
                if not reflex_decision and "whatsapp" in goal_lower and "send" in goal_lower and ("this" in goal_lower or "this file" in goal_lower):
                    import re
                    # Pattern: send this (file) to <contact> on whatsapp
                    match = re.search(r'send\s+this(?:\s+file)?\s+to\s+(.+?)\s+on\s+whatsapp', goal_lower)
                    if match:
                        contact = match.group(1).strip()
                        
                        import subprocess
                        import os
                        
                        print(f"[*] Getting selected file from file manager...")
                        
                        selected_file = None
                        
                        # Method 1: Copy selected file path using Ctrl+C in file manager
                        try:
                            # Use xdotool to simulate Ctrl+L (show path) + Ctrl+C (copy)
                            # Or get from clipboard if user already copied
                            result = subprocess.run(
                                ["xclip", "-selection", "clipboard", "-o"],
                                capture_output=True, text=True, timeout=2
                            )
                            clipboard = result.stdout.strip()
                            
                            # Check if clipboard contains a valid file path
                            if clipboard and os.path.isfile(clipboard):
                                selected_file = clipboard
                                print(f"[*] Got from clipboard: {selected_file}")
                        except:
                            pass
                        
                        # Method 2: Use DBus to get selected files from Nautilus
                        if not selected_file:
                            try:
                                result = subprocess.run(
                                    ["gdbus", "call", "--session", 
                                     "--dest", "org.gnome.Nautilus",
                                     "--object-path", "/org/gnome/Nautilus",
                                     "--method", "org.gnome.Nautilus.FileOperations.CopyURIs",
                                     "[]", ""],
                                    capture_output=True, text=True, timeout=2
                                )
                                # Parse URIs if available
                            except:
                                pass
                        
                        # Method 3: Get the most recently modified file in Downloads
                        if not selected_file:
                            try:
                                downloads = os.path.expanduser("~/Downloads")
                                files = [os.path.join(downloads, f) for f in os.listdir(downloads) 
                                        if os.path.isfile(os.path.join(downloads, f))]
                                if files:
                                    most_recent = max(files, key=os.path.getmtime)
                                    selected_file = most_recent
                                    print(f"[*] Using most recent file: {selected_file}")
                            except:
                                pass
                        
                        if selected_file:
                            print(f"[*] WHATSAPP SEND THIS REFLEX: Sending '{selected_file}' to '{contact}' -> Skipping Vision.")
                            reflex_decision = {
                                "action": "send_file",
                                "file_path": selected_file,
                                "recipient": contact,
                                "reason": "Reflex: WhatsApp Send This"
                            }
                        else:
                            print(f"[!] Could not detect selected file. Copy the file path to clipboard first (Ctrl+C on file).")
                
                # WHATSAPP GIF REFLEX: "send a funny gif to KRACK on whatsapp", "gif happy cat to KRACK on whatsapp"
                if not reflex_decision and "whatsapp" in goal_lower and "gif" in goal_lower and "file" not in goal_lower:
                    import re
                    # Pattern 1: "send (a)? <query> gif to <contact> on whatsapp"
                    # Pattern 2: "gif <query> to <contact> on whatsapp"
                    # Pattern 3: "send gif <query> to <contact> on whatsapp"
                    match = re.search(
                        r'(?:send\s+(?:a\s+)?(.+?)\s+gif|send\s+gif\s+(.+?)|gif\s+(.+?))\s+to\s+(.+?)\s+on\s+whatsapp',
                        goal_lower
                    )
                    if match:
                        query = (match.group(1) or match.group(2) or match.group(3) or "funny").strip()
                        contact = match.group(4).strip()
                        print(f"[*] WHATSAPP GIF REFLEX: Sending '{query}' GIF to '{contact}' -> Skipping Vision.")
                        reflex_decision = {
                            "action": "send_gif",
                            "query": query,
                            "recipient": contact,
                            "reason": "Reflex: WhatsApp GIF Send"
                        }
                
                if reflex_decision:
                    decision = reflex_decision
                    frame = None # No screenshot needed
                else:
                    # Check if browser is active window OR if goal is web-based - skip vision
                    active_win = actor.get_active_window()
                    is_browser = any(b in active_win.lower() for b in ["chrome", "chromium", "firefox", "browser"])
                    is_web_task = "whatsapp" in goal_lower  # WhatsApp = always web-based
                    
                    print(f"    - Window: '{active_win}' | Browser Mode: {is_browser} | Web Task: {is_web_task}")
                    
                    if is_browser or is_web_task:
                        print(f"  > [Web Mode] Skipping OmniParser, using DOM only...")
                        frame = None
                        detections = []
                    else:
                        # Step 1: Observe (Desktop mode)
                        frame = cap.capture()
                        
                        # Step 2: Perceive
                        print("  > [Desktop Mode] Detecting UI elements...")
                        # PREFER OMNIPARSER IF AVAILABLE
                        if brain.eyes:
                            import cv2
                            cv2.imwrite("current_screen.png", frame)
                            _, detections = brain.eyes.parse("current_screen.png")
                            print(f"    [OmniParser] Found {len(detections)} elements.")
                        else:
                             detections = detector.detect_and_ocr(frame)
                             print(f"    - Found {len(detections)} elements.")
                    
                    
                    # --- DOM CAPTURE (Web Mode) ---
                    dom_tree_str = ""
                    if is_browser:
                        print("    > Fetching Full DOM Tree (CDP)...")
                        import subprocess
                        try:
                            res = subprocess.run(
                                ["python3", "src/tools/get_dom.py"], 
                                capture_output=True, text=True, timeout=5
                            )
                            raw_dom = res.stdout.strip()
                            if raw_dom and raw_dom.startswith("{"):
                                 # Truncate if massive (context limit)
                                 if len(raw_dom) > 10000: 
                                     dom_tree_str = raw_dom[:10000] + "\n...(truncated)"
                                 else:
                                     dom_tree_str = raw_dom
                                 print(f"    [DOM] Captured {len(dom_tree_str)} chars of structure.")
                        except:
                            print("    [DOM] Failed to capture (Timeout/Error).")
                    # ------------------------------
    
                    # Step 3: Decide
                    print("  > Thinking...")
                    # Vision: Encode frame (skip if browser)
                    b64_image = encode_image(frame) if frame is not None else None
                    decision = brain.think(user_goal, detections, history, active_window=active_win, image_base64=b64_image, dom_tree=dom_tree_str)
                
                # --- CRASH FIX: Handle Brain Failures ---
                if not decision:
                    print("  > [!] Brain returned None (Hallucination/Error). Retrying in 2s...")
                    time.sleep(2)
                    continue

                action_type = decision.get("action")
                if action_type:
                    action_type = action_type.lower()
                
                # --- CLAWDBOT MULTI-STEP COMPLETION ---
                # If brain already completed the task via execute_multi_step
                if action_type == "done":
                    print(f"  > TASK COMPLETE: {decision.get('reason', decision.get('summary', 'Task finished'))}")
                    history.append(f"Completed: {user_goal}")
                    # Ask for new goal
                    print("\n[?] Task Complete. Enter new goal (or 'q' to quit):")
                    new_goal = input("> ").strip()
                    if new_goal.lower() == 'q':
                        print("[*] Exiting agent.")
                        break
                    user_goal = new_goal
                    continue
                
                # Removed Circuit Breaker as per user request to avoid premature stopping.
                
                reason = decision.get("reason", "No reason provided")
                print(f"  > DECISION: {action_type.upper()} - {reason}")
                
                # --- TRAINING INTERVENTION ---
                if args.train:
                    import json
                    print("\n=== 🛑 TRAINING INTERVENTION 🛑 ===")
                    print(f"Goal: {user_goal}")
                    print(f"Model Proposed Action: {json.dumps(decision, indent=2)}")
                    print("====================================")
                    
                    choice = input("Is this correct? (y = yes/save, n = fix, s = skip, q = quit): ").lower()
                    
                    if choice == 'q':
                        sys.exit(0)
                    elif choice == 'n':
                        print("Provide correct action (JSON) or type 'click 5' / 'type hello':")
                        correction = input("> ").strip()
                        
                        # Simple parsers for speed-training
                        if correction.startswith("click"):
                            try:
                                cid = int(correction.split()[1])
                                decision = {"action": "click", "selected_id": cid, "reason": "User Correction"}
                            except: pass
                        elif correction.startswith("type"):
                            text = " ".join(correction.split()[1:])
                            decision = {"action": "type", "text": text, "reason": "User Correction"}
                        elif correction.startswith("{"):
                            try:
                                decision = json.loads(correction)
                            except: print("[!] Invalid JSON, skipping save."); choice='s'
                        
                        # Update action type for execution below
                        action_type = decision.get("action", "").lower()
                        
                    if choice in ['y', 'n']:
                        screen_desc = []
                        for i, item in enumerate(detections):
                            label = item['label']
                            text = item.get('text', '').strip()
                            desc = f"ID {i}: {label}"
                            if text: desc += f" (Text: '{text}')"
                            screen_desc.append(desc)
                        input_str = f"Active Window: {active_win}. Visible Elements: {', '.join(screen_desc)}"
                        
                        example = {
                            "instruction": user_goal,
                            "input": input_str,
                            "output": json.dumps(decision)
                        }
                        
                        with open("training_data/manual_dataset.jsonl", "a") as f:
                            f.write(json.dumps(example) + "\n")
                        print("[+] Training example saved!")
                # -----------------------------
                
                if args.voice and mouth:
                    mouth.speak(reason)
                
                # Step 4: Act
                if action_type == "click":
                    selected_id = decision.get("selected_id")
                    target_desc = decision.get("target_description", "")
                    
                    # First try numeric ID from detections
                    if selected_id is not None and isinstance(selected_id, int) and 0 <= selected_id < len(detections):
                        target = detections[selected_id]
                        print(f"  > CLICKING: {target['label']} ('{target.get('text', '')}')")
                        
                        bbox = target["bbox"]
                        center_x = (bbox[0] + bbox[2]) // 2
                        center_y = (bbox[1] + bbox[3]) // 2
                        
                        abs_x = center_x + cap.monitor["left"]
                        abs_y = center_y + cap.monitor["top"]
                        
                        actor.click(abs_x, abs_y)
                        history.append(f"Clicked on {target['label']} ('{target.get('text', '')}')")
                        time.sleep(2) # Wait for UI
                    
                    # Fall back to description-based click using CDP
                    elif target_desc:
                        print(f"  > CLICK (by description): '{target_desc}'")
                        import subprocess
                        import json as json_mod
                        try:
                            # Use the CDP click tool
                            result = subprocess.run(
                                ["python3", "src/tools/cdp_click.py", "click", target_desc],
                                capture_output=True, text=True, timeout=10,
                                cwd="/home/harsha/Downloads/mightbe_done"
                            )
                            output = result.stdout.strip()
                            print(f"    [CDP] {output}")
                            
                            try:
                                resp = json_mod.loads(output)
                                if resp.get("success"):
                                    history.append(f"Clicked on '{target_desc}'")
                                else:
                                    print(f"    [!] Click failed: {resp.get('error')}")
                                    history.append(f"Failed to click '{target_desc}'")
                            except:
                                history.append(f"Clicked on '{target_desc}'")
                                
                        except Exception as e:
                            print(f"    [CDP Error] {e}")
                            history.append(f"Failed to click '{target_desc}'")
                        time.sleep(2)
                    else:
                        print("  > ERROR: Invalid ID for click.")
                
                elif action_type == "type":
                    text_to_type = decision.get("text", "")
                    print(f"  > TYPING: '{text_to_type}'")
                    actor.type_text(text_to_type)
                    actor.press_key("enter") 
                    history.append(f"Typed '{text_to_type}'")
                    time.sleep(1)
                
                elif action_type == "focus":
                    win_title = decision.get("window", "")
                    print(f"  > FOCUSING: '{win_title}'")
                    actor.focus_window(win_title)
                    history.append(f"Focused window '{win_title}'")
                    time.sleep(1)

                elif action_type == "launch":
                    app_cmd = decision.get("app", "")
                    if app_cmd.lower() in active_win.lower():
                        print(f"  > SKIP LAUNCH: '{app_cmd}' is already in active window title ('{active_win}').")
                        history.append(f"Skipped launch of '{app_cmd}' (Already active)")
                    else:
                        print(f"  > LAUNCHING: '{app_cmd}'")
                        actor.launch_app(app_cmd)
                        history.append(f"Launched '{app_cmd}'")
                        time.sleep(4) 

                elif action_type == "hotkey":
                    keys = decision.get("keys", [])
                    print(f"  > HOTKEY: {keys}")
                    actor.hotkey(keys)
                    history.append(f"Pressed hotkeys {keys}")
                    time.sleep(0.5)

                elif action_type == "wait":
                    print("  > WAITING...")
                    time.sleep(2)
                    history.append("Waited")
                    
                elif action_type == "done":
                    print("  > SUCCESS: Goal achieved.")
                    # Continuous Loop
                    print("\n[?] Task Complete. Enter new goal (or 'q' to quit):")
                    if args.voice and mouth: mouth.speak("Task complete. What's next?")
                    
                    try:
                        if args.voice and ears:
                            new_goal = ears.listen_once()
                            if not new_goal: new_goal = input("> ")
                        else:
                            new_goal = input("> ")
                        
                        if new_goal.lower() in ['q', 'quit', 'exit']:
                            sys.exit(0)
                        
                        if new_goal.strip():
                            user_goal = new_goal
                            history = [] 
                            print(f"[*] NEW GOAL: '{user_goal}'")
                            continue
                            
                    except KeyboardInterrupt:
                        raise # Bubble up to reset
                    except:
                        break
                    
                
                elif action_type == "wallpaper":
                    query = decision.get("query", "cat wallpaper")
                    print(f"  > WALLPAPER: Setting to '{query}' via workflow...")
                    import subprocess
                    try:
                        subprocess.run(["python3", "src/workflows/cat_wallpaper.py", "--query", query], check=True)
                        history.append(f"Set wallpaper to result for '{query}'")
                    except Exception as e:
                        print(f"    [Error] Wallpaper workflow failed: {e}")
                        history.append("Failed to set wallpaper")

                elif action_type == "read_whatsapp":
                    print("  > READ_WHATSAPP: Launching Bridge workflow...")
                    import subprocess
                    try:
                        result = subprocess.run(
                            ["python3", "src/workflows/read_whatsapp.py"], 
                            check=True,
                            capture_output=True,
                            text=True
                        )
                        print(result.stdout) 
                        output_text = result.stdout
                        history.append(f"Output from READ_WHATSAPP:\n{output_text}")
                        # If this was a reflex action, mark as done
                        if decision.get("reason", "").startswith("Reflex:"):
                            print("  > REFLEX COMPLETE: WhatsApp read.")
                            action_type = "done"  # Trigger done handler
                    except Exception as e:
                        print(f"    [Error] WhatsApp workflow failed: {e}")
                        history.append(f"Failed to read WhatsApp: {e}")
                
                elif action_type == "send_message":
                    # WhatsApp HTTP Bridge API (localhost:3001)
                    recipient = decision.get("recipient", decision.get("contact", decision.get("target", "")))
                    msg = decision.get("message", "")
                    print(f"  > SEND_MESSAGE: Sending '{msg}' to '{recipient}'...")
                    
                    try:
                        import requests as req
                        payload = {"searchName": recipient, "message": msg}
                        resp = req.post("http://localhost:3001/send", json=payload, timeout=30)
                        result = resp.json()
                        
                        if result.get("success"):
                            print(f"    [+] Message sent successfully!")
                            history.append(f"Sent '{msg}' to {recipient}")
                            
                            # Success - prompt for new goal
                            print("\n[?] Task Complete. Enter new goal (or 'q' to quit):")
                            if args.voice and mouth: mouth.speak("Message sent. What's next?")
                            
                            history = []  # Reset history
                            try:
                                if args.voice and ears:
                                    new_goal = ears.listen_once()
                                    if not new_goal: new_goal = input("> ")
                                else:
                                    new_goal = input("> ")
                                
                                if new_goal.lower() in ['q', 'quit', 'exit']:
                                    sys.exit(0)
                                
                                if new_goal.strip():
                                    user_goal = new_goal
                                    print(f"[*] NEW GOAL: '{user_goal}'")
                                    break  # Exit inner loop, restart with new goal
                            except KeyboardInterrupt:
                                raise
                        else:
                            print(f"    [!] Failed: {result.get('error')}")
                            history.append(f"Failed to send message: {result.get('error')}")
                    except Exception as e:
                        print(f"    [Error] Send failed: {e}")
                        history.append(f"Failed to send: {e}")
                
                elif action_type == "tool" or (hasattr(brain, "tools") and action_type in brain.tools.tools_registry):
                    
                    # Normalize: Handle both wrapped "tool" action and direct "tool_name" action
                    if action_type == "tool":
                        tool_name = decision.get("tool_name", "")
                        tool_args = decision.get("tool_args", {})
                    else:
                        tool_name = action_type
                        tool_args = {k: v for k, v in decision.items() if k not in ["action", "reason", "bbox"]}

                    print(f"  > TOOL EXECUTION: {tool_name} with {tool_args}")
                    
                    if hasattr(brain, "tools"):
                        result = brain.tools.execute(tool_name, **tool_args)
                        print(f"    [Tool Result]: {str(result)[:200]}")
                        history.append(f"Executed tool '{tool_name}': {str(result)[:100]}...")
                        
                        if result.get("success"):
                            # If tool was successful, maybe task is done or needs follow up
                            pass
                        else:
                            print(f"    [!] Tool failed: {result.get('error')}")
                    else:
                        print("    [!] Brain has no tools initialized!")

                elif action_type == "send_file":
                    # Send file via WhatsApp HTTP Bridge API (localhost:3001)
                    recipient = decision.get("recipient", decision.get("contact", decision.get("target", "")))
                    file_path = decision.get("file_path", decision.get("path", decision.get("file", "")))
                    caption = decision.get("caption", "")
                    print(f"  > SEND_FILE: Sending '{file_path}' to '{recipient}'...")
                    
                    try:
                        import requests as req
                        payload = {"searchName": recipient, "mediaPath": file_path}
                        if caption:
                            payload["message"] = caption
                        resp = req.post("http://localhost:3001/send", json=payload, timeout=60)
                        result = resp.json()
                        
                        if result.get("success"):
                            print(f"    [+] File sent successfully!")
                            history.append(f"Sent file '{file_path}' to {recipient}")
                            
                            # Success - prompt for new goal
                            print("\n[?] Task Complete. Enter new goal (or 'q' to quit):")
                            if args.voice and mouth: mouth.speak("File sent. What's next?")
                            
                            history = []  # Reset history
                            try:
                                if args.voice and ears:
                                    new_goal = ears.listen_once()
                                    if not new_goal: new_goal = input("> ")
                                else:
                                    new_goal = input("> ")
                                
                                if new_goal.lower() in ['q', 'quit', 'exit']:
                                    sys.exit(0)
                                
                                if new_goal.strip():
                                    user_goal = new_goal
                                    print(f"[*] NEW GOAL: '{user_goal}'")
                                    break  # Exit inner loop, restart with new goal
                            except KeyboardInterrupt:
                                raise
                        else:
                            print(f"    [!] Failed: {result.get('error')}")
                            history.append(f"Failed to send file: {result.get('error')}")
                            
                            print("\n[!] File send failed. Enter new goal (or 'q' to quit):")
                            try:
                                new_goal = input("> ")
                                if new_goal.lower() in ['q', 'quit', 'exit']:
                                    sys.exit(0)
                                if new_goal.strip():
                                    user_goal = new_goal
                                    print(f"[*] NEW GOAL: '{user_goal}'")
                                    break
                            except KeyboardInterrupt:
                                raise
                    except Exception as e:
                        print(f"    [Error] Send file failed: {e}")
                        history.append(f"Failed to send file: {e}")
                        
                        print("\n[!] Error occurred. Enter new goal (or 'q' to quit):")
                        try:
                            new_goal = input("> ")
                            if new_goal.lower() in ['q', 'quit', 'exit']:
                                sys.exit(0)
                            if new_goal.strip():
                                user_goal = new_goal
                                print(f"[*] NEW GOAL: '{user_goal}'")
                                break
                        except KeyboardInterrupt:
                            raise
                
                elif action_type == "send_gif":
                    # WhatsApp GIF sending via bridge's built-in Tenor picker (Puppeteer UI automation)
                    query = decision.get("query", "funny")
                    recipient = decision.get("recipient", decision.get("contact", ""))
                    print(f"  > SEND_GIF: Searching '{query}' GIF for '{recipient}'...")
                    
                    try:
                        import requests as req
                        payload = {"searchName": recipient, "query": query}
                        resp = req.post("http://localhost:3001/send-gif", json=payload, timeout=30)
                        result = resp.json()
                        
                        if result.get("success"):
                            print(f"    [+] GIF sent successfully!")
                            history.append(f"Sent '{query}' GIF to {recipient} via WhatsApp picker")
                            
                            # Success - prompt for new goal
                            print("\n[?] Task Complete. Enter new goal (or 'q' to quit):")
                            if args.voice and mouth: mouth.speak("GIF sent. What's next?")
                            
                            history = []  # Reset history
                            try:
                                if args.voice and ears:
                                    new_goal = ears.listen_once()
                                    if not new_goal: new_goal = input("> ")
                                else:
                                    new_goal = input("> ")
                                
                                if new_goal.lower() in ['q', 'quit', 'exit']:
                                    sys.exit(0)
                                
                                if new_goal.strip():
                                    user_goal = new_goal
                                    print(f"[*] NEW GOAL: '{user_goal}'")
                                    break  # Exit inner loop, restart with new goal
                            except KeyboardInterrupt:
                                raise
                        else:
                            print(f"    [!] GIF send failed: {result.get('error')}")
                            history.append(f"Failed to send GIF: {result.get('error')}")
                    except Exception as e:
                        print(f"    [Error] GIF send failed: {e}")
                        history.append(f"Failed to send GIF: {e}")
                
                elif action_type == "send_whatsapp":
                    contact = decision.get("contact", "")
                    msg = decision.get("message", "")
                    print(f"  > SEND_WHATSAPP: Sending '{msg}' to '{contact}'...")
                    try:
                        import requests as req
                        payload = {"searchName": contact, "message": msg}
                        resp = req.post("http://localhost:3001/send", json=payload, timeout=30)
                        result = resp.json()
                        
                        if result.get("success"):
                            print(f"    [+] Message sent to {contact}!")
                            history.append(f"Sent '{msg}' to {contact}")
                        else:
                            print(f"    [!] Failed: {result.get('error')}")
                            history.append(f"Failed: {result.get('error')}")
                        
                        # Prompt for new goal
                        print("\n[?] Task Complete. Enter new goal (or 'q' to quit):")
                        if args.voice and mouth: mouth.speak("Message sent. What's next?")
                        
                        history = []  # Reset history
                        try:
                            if args.voice and ears:
                                new_goal = ears.listen_once()
                                if not new_goal: new_goal = input("> ")
                            else:
                                new_goal = input("> ")
                            
                            if new_goal.lower() in ['q', 'quit', 'exit']:
                                sys.exit(0)
                            
                            if new_goal.strip():
                                user_goal = new_goal
                                print(f"[*] NEW GOAL: '{user_goal}'")
                                break
                        except KeyboardInterrupt:
                            raise
                    except Exception as e:
                        print(f"    [Error] Send failed: {e}")
                        history.append(f"Failed to send message: {e}")

                elif action_type == "execute_whatsapp_js":
                    code = decision.get("code", "")
                    print(f"  > EXECUTE_JS: Running '{code}'...")
                    import subprocess
                    try:
                        result = subprocess.run(
                            ["python3", "src/workflows/exec_whatsapp_js.py", "--js", code], 
                            check=True, 
                            capture_output=True, 
                            text=True
                        )
                        print(result.stdout)
                        history.append(f"JS Result:\n{result.stdout}")
                    except Exception as e:
                        print(f"    [Error] JS execution failed: {e}")
                        history.append(f"JS Failed: {e}")

                elif action_type == "search":
                    query = decision.get("query", "")
                    print(f"  > SEARCHING: '{query}'...")
                    from src.tools.internet import search_web
                    try:
                        result = search_web(query)
                        print(f"    [Result] {result[:200]}...") 
                        history.append(f"Search Results for '{query}':\n{result}")
                    except Exception as e:
                        print(f"    [Error] Search failed: {e}")
                        history.append(f"Search failed: {e}")

                elif action_type == "browse":
                    url = decision.get("url", "google.com")
                    print(f"  > BROWSING: Launching session at '{url}'...")
                    import subprocess
                    try:
                        subprocess.run(["python3", "src/workflows/launch_browser.py", "--url", url], check=False)
                        history.append(f"Launched browser at {url}")
                        time.sleep(5)
                        
                        # If this was a reflex action, complete and prompt for new goal
                        if decision.get("reason", "").startswith("Reflex:"):
                            print("  > REFLEX COMPLETE: Browser opened.")
                            print("\n[?] Task Complete. Enter new goal (or 'q' to quit):")
                            if args.voice and mouth: mouth.speak("Browser opened. What's next?")
                            
                            history = []  # Reset history
                            try:
                                if args.voice and ears:
                                    new_goal = ears.listen_once()
                                    if not new_goal: new_goal = input("> ")
                                else:
                                    new_goal = input("> ")
                                
                                if new_goal.lower() in ['q', 'quit', 'exit']:
                                    sys.exit(0)
                                
                                if new_goal.strip():
                                    user_goal = new_goal
                                    print(f"[*] NEW GOAL: '{user_goal}'")
                                    break  # Exit inner loop, restart with new goal
                            except KeyboardInterrupt:
                                raise  # Bubble up to outer handler
                    except Exception as e:
                        print(f"    [Error] Browser launch failed: {e}")
                        history.append(f"Browser failed: {e}")

                elif action_type == "say":
                    text = decision.get("text", "")
                    print(f"\n[🤖 AGENT]: {text}\n")
                    if args.voice and mouth: mouth.speak(text)
                    history.append(f"Agent said: {text}")

                # --- GENERIC CODE EXECUTION ---
                elif action_type == "run_code":
                    code_snippet = decision.get("code", "")
                    print(f"[Skill] Executing Generated Python Code ({len(code_snippet)} chars)...")
                    
                    import os
                    temp_script = "src/temp_skill.py"
                    header = "import sys; import os; sys.path.append(os.getcwd());\n"
                    with open(temp_script, "w") as f:
                        f.write(header + code_snippet)
                    
                    import subprocess
                    try:
                        subprocess.run(["python3", temp_script], check=True)
                        history.append("Executed generated code successfully.")
                    except subprocess.CalledProcessError as e:
                        print(f"    [Exec Error] Script failed: {e}")
                        history.append("Generated code failed.")
                
                # --- SHELL COMMAND EXECUTION ---
                elif action_type == "shell":
                    command = decision.get("command", "")
                    print(f"  > SHELL: Executing '{command}'...")
                    
                    # Safety check - block dangerous commands
                    dangerous = ["rm -rf /", "rm -rf /*", ":(){ :|:& };:", "mkfs", "dd if=", "> /dev/sd"]
                    is_dangerous = any(d in command for d in dangerous)
                    
                    if is_dangerous:
                        print(f"    [!] BLOCKED: Dangerous command detected!")
                        history.append(f"Shell command blocked (dangerous): {command}")
                    else:
                        import subprocess
                        import os
                        try:
                            result = subprocess.run(
                                command, 
                                shell=True, 
                                capture_output=True, 
                                text=True,
                                timeout=30,
                                cwd=os.getcwd(),
                                env=os.environ.copy()  # Pass DISPLAY and other env vars for xdotool
                            )
                            output = result.stdout.strip() or result.stderr.strip() or "(no output)"
                            print(f"    [+] Output: {output[:200]}")
                            history.append(f"Shell '{command}' -> {output[:100]}")
                            
                            if result.returncode != 0:
                                print(f"    [!] Command exited with code {result.returncode}")
                            else:
                                # Shell command succeeded - mark as done and break
                                print("  > SUCCESS: Shell command completed.")
                                print("\n[?] Task Complete. Enter new goal (or 'q' to quit):")
                                history = []
                                break  # Exit inner loop to wait for new goal
                        except subprocess.TimeoutExpired:
                            print(f"    [!] Command timed out after 30s")
                            history.append(f"Shell command timed out: {command}")
                        except Exception as e:
                            print(f"    [!] Shell error: {e}")
                            history.append(f"Shell error: {e}")
                
                elif action_type == "done":
                    print("  > SUCCESS: Goal achieved.")
                    print("\n[?] Task Complete. Enter new goal (or 'q' to quit):")
                    if args.voice and mouth: mouth.speak("Task complete. What's next?")
                    
                    history = [] # Reset for next
                    while True:
                        try:
                            if args.voice and ears:
                                new_goal = ears.listen_once()
                                if not new_goal: new_goal = input("> ")
                            else:
                                new_goal = input("> ")
                            
                            if new_goal.lower() in ['q', 'quit', 'exit']:
                                sys.exit(0)
                            
                            if new_goal.strip():
                                user_goal = new_goal
                                print(f"[*] NEW GOAL: '{user_goal}'")
                                break # Break input loop -> Continue outer loop
                        except KeyboardInterrupt:
                            sys.exit(0)
                
                else:
                    print(f"  > UNKNOWN ACTION: {action_type}")
                    history.append(f"Unknown action {action_type}")
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\n\n[!] Interrupted by user (Ctrl+C). Resetting Agent...")
            history = []
            print("\n[?] Enter new goal (or 'q' to quit):")
            try:
                if args.voice and ears:
                     new_goal = ears.listen_once()
                     if not new_goal: new_goal = input("> ")
                else:
                     new_goal = input("> ")
                
                if new_goal.lower() in ['q', 'quit']: sys.exit(0)
                if new_goal.strip():
                    user_goal = new_goal
                    print(f"[*] NEW GOAL: '{user_goal}'")
                    continue
            except KeyboardInterrupt:
                print("[!] Force Quit.")
                sys.exit(0)
        except Exception as e:
            print(f"\n[!] Critical Main Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
