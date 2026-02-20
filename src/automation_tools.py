"""
ARIA Automation Tools Registry

This module provides all automation capabilities that ARIA can execute.
Each tool is a callable function that the VLM can invoke to perform real actions.
"""

import os
import subprocess
import shutil
import platform
import socket
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import asyncio
from src.bridges.telegram_bridge import telegram_bridge
from src.bridges.email_bridge import email_bridge

try:
    import psutil
except ImportError:
    psutil = None

class AutomationTools:
    """
    Central registry of all automation tools available to ARIA.
    Each method is an executable action the agent can take.
    """
    
    def __init__(self):
        self.tools_registry = self._build_registry()
    
    def _build_registry(self) -> Dict[str, Dict]:
        """Build the tools registry with metadata for the VLM."""
        registry = {
            # ===== WEB & YOUTUBE =====
            "youtube_search": {
                "description": "Search YouTube and play a video",
                "parameters": ["query"],
                "example": "youtube_search('lofi music')"
            },
            "youtube_download": {
                "description": "Download a YouTube video or audio",
                "parameters": ["url", "audio_only"],
                "example": "youtube_download('https://youtube.com/...', audio_only=True)"
            },
            "web_request": {
                "description": "Fetch content from a URL",
                "parameters": ["url"],
                "example": "web_request('https://api.example.com/data')"
            },
            
            # ===== MESSAGING & COMMS =====
            "whatsapp_send": {
                "description": "Send a WhatsApp message (legacy pywhatkit method)",
                "parameters": ["phone_number", "message"],
                "example": "whatsapp_send('+1234567890', 'Hello!')"
            },
            "email_send": {
                "description": "Send an email",
                "parameters": ["to", "subject", "body"],
                "example": "email_send('user@example.com', 'Subject', 'Body text')"
            },
            "email_read": {
                "description": "Read recent emails",
                "parameters": ["limit", "unread_only"],
                "example": "email_read(limit=5)"
            },
            "send_telegram": {
                "description": "Send a Telegram message",
                "parameters": ["chat_id", "text"],
                "example": "send_telegram('123454321', 'Hello from ARIA')"
            },
            "read_telegram": {
                "description": "Read recent Telegram messages",
                "parameters": ["limit"],
                "example": "read_telegram(5)"
            },
            
            # ===== GUI & DESKTOP =====
            "click": {
                "description": "Click at screen coordinates",
                "parameters": ["x", "y"],
                "example": "click(500, 300)"
            },
            "type_text": {
                "description": "Type text using keyboard",
                "parameters": ["text"],
                "example": "type_text('Hello world')"
            },
            "hotkey": {
                "description": "Press keyboard shortcut",
                "parameters": ["keys"],
                "example": "hotkey('ctrl', 'c')"
            },
            "screenshot": {
                "description": "Take a screenshot",
                "parameters": ["filename"],
                "example": "screenshot('screen.png')"
            },
            "move_window": {
                "description": "Move or resize a window",
                "parameters": ["window_name", "x", "y", "width", "height"],
                "example": "move_window('Firefox', 0, 0, 1920, 1080)"
            },
            "focus_window": {
                "description": "Focus/activate a window",
                "parameters": ["window_name"],
                "example": "focus_window('Chrome')"
            },
            
            # ===== OS & SYSTEM =====
            "run_command": {
                "description": "Run a shell command",
                "parameters": ["command"],
                "example": "run_command('ls -la')"
            },
            "open_app": {
                "description": "Open an application",
                "parameters": ["app_name"],
                "example": "open_app('firefox')"
            },
            "notify": {
                "description": "Show desktop notification",
                "parameters": ["title", "message"],
                "example": "notify('Alert', 'Task completed!')"
            },
            "set_volume": {
                "description": "Set system volume",
                "parameters": ["level"],
                "example": "set_volume(50)"
            },
            "set_brightness": {
                "description": "Set screen brightness",
                "parameters": ["level"],
                "example": "set_brightness(80)"
            },
            "get_system_info": {
                "description": "Get CPU, RAM, and Disk usage",
                "parameters": [],
                "example": "get_system_info()"
            },
            "list_processes": {
                "description": "List running processes",
                "parameters": ["filter_name"],
                "example": "list_processes('chrome')"
            },
            "kill_process": {
                "description": "Kill a process by name or PID",
                "parameters": ["target"],
                "example": "kill_process('firefox')"
            },
            
            # ===== IMPLEMENTATION: PRODUCTIVITY & CLOUD =====
            "github_ops": {
                "description": "Interact with GitHub (issues, prs, checks)",
                "parameters": ["operation", "repo", "additional_args"],
                "example": "github_ops('list_issues', 'owner/repo')"
            },
            "discord_send": {
                "description": "Send message to Discord webhook",
                "parameters": ["webhook_url", "content"],
                "example": "discord_send('https://discord.com/...', 'Build success!')"
            },
            "weather_check": {
                "description": "Check current weather",
                "parameters": ["location"],
                "example": "weather_check('London')"
            },

            # ===== IMPLEMENTATION: ADVANCED SYSTEM =====
            "manage_tmux": {
                "description": "Manage tmux sessions",
                "parameters": ["action", "session"],
                "example": "manage_tmux('new', 'aria_dev')"
            },
            "read_pdf": {
                "description": "Read text from PDF",
                "parameters": ["path"],
                "example": "read_pdf('/tmp/doc.pdf')"
            },

            # ===== FILES =====
            "create_file": {
                "description": "Create a new file with content",
                "parameters": ["path", "content"],
                "example": "create_file('/tmp/note.txt', 'Hello')"
            },
            "read_file": {
                "description": "Read file contents",
                "parameters": ["path"],
                "example": "read_file('/tmp/note.txt')"
            },
            "edit_file": {
                "description": "Replace text in a file",
                "parameters": ["path", "old_text", "new_text"],
                "example": "edit_file('config.py', 'DEBUG=False', 'DEBUG=True')"
            },
            "copy_file": {
                "description": "Copy a file",
                "parameters": ["source", "destination"],
                "example": "copy_file('/tmp/a.txt', '/tmp/b.txt')"
            },
            "move_file": {
                "description": "Move/rename a file",
                "parameters": ["source", "destination"],
                "example": "move_file('/tmp/old.txt', '/tmp/new.txt')"
            },
            "delete_file": {
                "description": "Delete a file",
                "parameters": ["path"],
                "example": "delete_file('/tmp/unwanted.txt')"
            },
            "list_directory": {
                "description": "List files in a directory",
                "parameters": ["path"],
                "example": "list_directory('/home/user')"
            },
            
            # ===== MEDIA =====
            "play_spotify": {
                "description": "Play music on Spotify",
                "parameters": ["query"],
                "example": "play_spotify('Bohemian Rhapsody')"
            },
            "media_control": {
                "description": "Control media playback (play/pause/next/prev)",
                "parameters": ["action"],
                "example": "media_control('pause')"
            },
        }
        return registry
    
    def get_tools_prompt(self) -> str:
        """Generate a prompt describing all available tools for the VLM."""
        lines = ["AVAILABLE TOOLS:"]
        for name, info in self.tools_registry.items():
            params = ", ".join(info["parameters"])
            lines.append(f"- {name}({params}): {info['description']}")
        return "\n".join(lines)
    
    # ===== IMPLEMENTATION: WEB & YOUTUBE =====
    
    def youtube_search(self, query: str) -> Dict[str, Any]:
        """Search YouTube via API and auto-play the first video result."""
        try:
            # Get YouTube API key
            api_key = os.environ.get("YOUTUBE_API_KEY", "")
            if not api_key:
                # Try loading from personal context
                try:
                    import json
                    ctx_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                            "data", "personal_context.json")
                    with open(ctx_path) as f:
                        ctx = json.load(f)
                    api_key = ctx.get("api_keys", {}).get("youtube", "")
                except Exception:
                    pass

            url = None
            title = query

            if api_key:
                # Use YouTube Data API v3
                from googleapiclient.discovery import build
                youtube = build("youtube", "v3", developerKey=api_key)
                request = youtube.search().list(
                    part="snippet",
                    q=query,
                    type="video",
                    maxResults=1
                )
                response = request.execute()

                if response.get("items"):
                    item = response["items"][0]
                    video_id = item["id"]["videoId"]
                    title = item["snippet"]["title"]
                    url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"

            if not url:
                # Fallback: use yt-dlp to find video ID
                try:
                    id_result = subprocess.run(
                        ["yt-dlp", f"ytsearch1:{query}", "--get-id", "--get-title", "--no-playlist"],
                        capture_output=True, text=True, timeout=15
                    )
                    lines = id_result.stdout.strip().split('\n')
                    if id_result.returncode == 0 and lines:
                        title = lines[0] if len(lines) > 1 else query
                        video_id = lines[-1].strip()
                        if video_id and len(video_id) < 20:
                            url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
                except Exception:
                    pass

            if not url:
                # Last fallback: open search page
                url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"

            # Open the URL
            subprocess.Popen(["xdg-open", url],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)

            # Auto-play: wait for page to load, then click video + press space
            import threading
            def _force_play():
                import time
                time.sleep(5)  # Wait for browser to load the page
                try:
                    # Find the YouTube window
                    find = subprocess.run(
                        ["xdotool", "search", "--name", "YouTube"],
                        capture_output=True, text=True, timeout=5
                    )
                    wids = [w.strip() for w in find.stdout.strip().split('\n') if w.strip()]
                    if wids:
                        wid = wids[0]
                        # Activate and focus
                        subprocess.run(["xdotool", "windowactivate", "--sync", wid], timeout=3)
                        time.sleep(0.3)
                        subprocess.run(["xdotool", "windowfocus", "--sync", wid], timeout=3)
                        time.sleep(0.3)

                        # Get window geometry and click the video area
                        import re
                        geom = subprocess.run(
                            ["xdotool", "getwindowgeometry", wid],
                            capture_output=True, text=True, timeout=3
                        )
                        geo_match = re.search(r'Geometry:\s*(\d+)x(\d+)', geom.stdout)
                        if geo_match:
                            w, h = int(geo_match.group(1)), int(geo_match.group(2))
                            # Click the video area (upper-center where the player is)
                            subprocess.run(
                                ["xdotool", "mousemove", "--window", wid,
                                 str(w // 2), str(h // 3), "click", "1"],
                                timeout=3
                            )
                            time.sleep(0.5)

                        # Press 'k' (YouTube play/pause shortcut — works even without focus on player)
                        subprocess.run(["xdotool", "key", "--window", wid, "k"], timeout=5)
                except Exception:
                    pass  # Best effort — don't crash if auto-play fails

            # Run auto-play in background thread so it doesn't block
            threading.Thread(target=_force_play, daemon=True).start()

            return {"success": True, "action": "youtube_play",
                    "query": query, "title": title, "url": url}

        except Exception as e:
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            subprocess.Popen(["xdg-open", url],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return {"success": True, "action": "youtube_search", "query": query}
    
    def youtube_download(self, url: str, audio_only: bool = False) -> Dict[str, Any]:
        """Download YouTube video/audio."""
        try:
            output_dir = os.path.expanduser("~/Downloads")
            if audio_only:
                cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "-o", f"{output_dir}/%(title)s.%(ext)s", url]
            else:
                cmd = ["yt-dlp", "-o", f"{output_dir}/%(title)s.%(ext)s", url]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {"success": result.returncode == 0, "output": result.stdout}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def web_request(self, url: str) -> Dict[str, Any]:
        """Fetch content from URL."""
        try:
            import requests
            response = requests.get(url, timeout=10)
            return {"success": True, "status": response.status_code, "content": response.text[:1000]}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== IMPLEMENTATION: MESSAGING =====
    
    def whatsapp_send(self, phone_number: str, message: str) -> Dict[str, Any]:
        """Send WhatsApp message via pywhatkit (legacy)."""
        try:
            import pywhatkit
            # Instant send (requires WhatsApp Web to be logged in)
            pywhatkit.sendwhatmsg_instantly(phone_number, message, wait_time=10)
            return {"success": True, "action": "whatsapp_send", "to": phone_number}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def email_send(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """Send email via SMTP Bridge."""
        return email_bridge.send_email(to, subject, body)

    def email_read(self, limit: int = 5, unread_only: bool = True) -> Dict[str, Any]:
        """Read emails via IMAP Bridge."""
        return email_bridge.read_emails(limit, unread_only)

    def send_telegram(self, chat_id: str, text: str) -> Dict[str, Any]:
        """Send Telegram message via Bridge."""
        try:
            result = asyncio.run(telegram_bridge.send_message(chat_id, text))
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_telegram(self, limit: int = 5) -> Dict[str, Any]:
        """Read recent Telegram messages."""
        try:
            messages = asyncio.run(telegram_bridge.get_recent_messages(limit))
            return {"success": True, "messages": messages, "count": len(messages)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== IMPLEMENTATION: GUI & DESKTOP =====
    
    def click(self, x: int, y: int) -> Dict[str, Any]:
        """Click at coordinates using xdotool."""
        try:
            subprocess.run(["xdotool", "mousemove", str(x), str(y)], check=True)
            subprocess.run(["xdotool", "click", "1"], check=True)
            return {"success": True, "action": "click", "x": x, "y": y}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def type_text(self, text: str) -> Dict[str, Any]:
        """Type text using xdotool."""
        try:
            subprocess.run(["xdotool", "type", "--clearmodifiers", text], check=True)
            return {"success": True, "action": "type", "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def hotkey(self, *keys_pos: str, keys: list = None) -> Dict[str, Any]:
        """Press keyboard shortcut using xdotool."""
        try:
            # Accept both hotkey("ctrl", "c") and hotkey(keys=["ctrl", "c"])
            actual_keys = list(keys_pos) if keys_pos else (keys if keys else [])
            if not actual_keys:
                return {"success": False, "error": "No keys provided"}
            key_combo = "+".join(actual_keys)
            subprocess.run(["xdotool", "key", key_combo], check=True)
            return {"success": True, "action": "hotkey", "keys": actual_keys}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def screenshot(self, filename: str = "/tmp/screenshot.png") -> Dict[str, Any]:
        """Take screenshot using scrot or gnome-screenshot."""
        try:
            subprocess.run(["scrot", filename], check=True)
            return {"success": True, "action": "screenshot", "path": filename}
        except FileNotFoundError:
            try:
                subprocess.run(["gnome-screenshot", "-f", filename], check=True)
                return {"success": True, "action": "screenshot", "path": filename}
            except Exception as e:
                return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def move_window(self, window_name: str, x: int, y: int, width: int, height: int) -> Dict[str, Any]:
        """Move/resize window using wmctrl."""
        try:
            subprocess.run(["wmctrl", "-r", window_name, "-e", f"0,{x},{y},{width},{height}"], check=True)
            return {"success": True, "action": "move_window", "window": window_name}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def focus_window(self, window_name: str) -> Dict[str, Any]:
        """Focus window using wmctrl."""
        try:
            subprocess.run(["wmctrl", "-a", window_name], check=True)
            return {"success": True, "action": "focus_window", "window": window_name}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== IMPLEMENTATION: OS & SYSTEM (EXTENDED) =====
    
    def run_command(self, command: str) -> Dict[str, Any]:
        """Run shell command."""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def open_app(self, app_name: str) -> Dict[str, Any]:
        """Open application."""
        try:
            subprocess.Popen([app_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"success": True, "action": "open_app", "app": app_name}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def notify(self, title: str, message: str) -> Dict[str, Any]:
        """Show desktop notification."""
        try:
            subprocess.run(["notify-send", title, message], check=True)
            return {"success": True, "action": "notify", "title": title}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def set_volume(self, level: int) -> Dict[str, Any]:
        """Set system volume (0-100)."""
        try:
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"], check=True)
            return {"success": True, "action": "set_volume", "level": level}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def set_brightness(self, level: int) -> Dict[str, Any]:
        """Set screen brightness (0-100)."""
        try:
            subprocess.run(["brightnessctl", "set", f"{level}%"], check=True)
            return {"success": True, "action": "set_brightness", "level": level}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_system_info(self) -> Dict[str, Any]:
        """Get system resource usage."""
        try:
            if not psutil:
                return {"success": False, "error": "psutil not installed"}
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            info = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "platform": platform.platform(),
                "hostname": socket.gethostname()
            }
            return {"success": True, "info": info}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_processes(self, filter_name: str = "") -> Dict[str, Any]:
        """List processes, optionally filtered by name."""
        try:
            if not psutil:
                return {"success": False, "error": "psutil not installed"}
            
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'username']):
                try:
                    if filter_name.lower() in proc.info['name'].lower():
                        processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            # Limit results
            return {"success": True, "processes": processes[:20], "count": len(processes)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def kill_process(self, target: str) -> Dict[str, Any]:
        """Kill process by PID (str/int) or name (str)."""
        try:
            if not psutil:
                return {"success": False, "error": "psutil not installed"}
            
            # Try as PID
            try:
                pid = int(target)
                p = psutil.Process(pid)
                p.terminate()
                return {"success": True, "action": "kill_process", "pid": pid}
            except ValueError:
                # Try as name
                killed = []
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if proc.info['name'].lower() == target.lower():
                            proc.terminate()
                            killed.append(proc.info['pid'])
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                if killed:
                    return {"success": True, "action": "kill_process", "target": target, "killed_pids": killed}
                else:
                    return {"success": False, "error": f"No process found matching '{target}'"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ===== IMPLEMENTATION: PRODUCTIVITY & CLOUD =====

    def github_ops(self, operation: str, repo: str = "", additional_args: List[str] = []) -> Dict[str, Any]:
        """Interact with GitHub via gh CLI.
        Operations: list_issues, list_prs, get_issue, checks, run_log
        """
        try:
            if not shutil.which("gh"):
                return {"success": False, "error": "GitHub CLI (gh) not installed"}

            cmd = ["gh"]
            if operation == "list_issues":
                cmd.extend(["issue", "list", "--limit", "10", "--json", "number,title,state"])
            elif operation == "list_prs":
                cmd.extend(["pr", "list", "--limit", "10", "--json", "number,title,state,checksStatus"])
            elif operation == "context":
                # Get current repo context
                cmd = ["gh", "repo", "view", "--json", "name,owner,description"]
            elif operation == "run_log":
                if not additional_args: return {"success": False, "error": "Run ID required"}
                cmd.extend(["run", "view", additional_args[0], "--log-failed"])
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
            
            if repo:
                cmd.extend(["--repo", repo])
                
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return {"success": False, "error": result.stderr}
                
            try:
                data = json.loads(result.stdout)
                return {"success": True, "data": data}
            except:
                return {"success": True, "output": result.stdout}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    def discord_send(self, webhook_url: str, content: str = "", username: str = "ARIA") -> Dict[str, Any]:
        """Send message to Discord via Webhook."""
        try:
            import requests
            payload = {"content": content, "username": username}
            resp = requests.post(webhook_url, json=payload)
            return {"success": resp.status_code in [200, 204], "status": resp.status_code}
        except ImportError:
            return {"success": False, "error": "requests module missing"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def weather_check(self, location: str = "") -> Dict[str, Any]:
        """Check weather via wttr.in."""
        try:
            import requests
            url = f"https://wttr.in/{location}?format=3"
            resp = requests.get(url)
            return {"success": True, "weather": resp.text.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    # ===== IMPLEMENTATION: ADVANCED SYSTEM =====
    
    def manage_tmux(self, action: str, session: str = "aria") -> Dict[str, Any]:
        """Manage tmux sessions."""
        try:
            if not shutil.which("tmux"):
                return {"success": False, "error": "tmux not installed"}
                
            if action == "new":
                cmd = f"tmux new-session -d -s {session}"
            elif action == "kill":
                cmd = f"tmux kill-session -t {session}"
            elif action == "list":
                cmd = "tmux list-sessions"
            elif action == "capture":
                cmd = f"tmux capture-pane -t {session} -p"
            else:
                return {"success": False, "error": "Unknown tmux action"}
                
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return {"success": res.returncode == 0, "output": res.stdout or res.stderr}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def read_pdf(self, path: str) -> Dict[str, Any]:
        """Extract text from PDF (requires pypdf or pdftotext)."""
        # Try generic pdftotext first
        if shutil.which("pdftotext"):
            res = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True)
            if res.returncode == 0:
                return {"success": True, "text": res.stdout[:10000] + "..." if len(res.stdout) > 10000 else res.stdout}
        
        return {"success": False, "error": "No PDF reader tool found (install poppler-utils)"}

    # ===== IMPLEMENTATION: FILES (EXTENDED) =====

    def edit_file(self, path: str, old_text: str, new_text: str) -> Dict[str, Any]:
        """Replace exact text in a file."""
        try:
            if not os.path.exists(path):
                return {"success": False, "error": "File not found"}
            
            with open(path, 'r') as f:
                content = f.read()
            
            if old_text not in content:
                # Try fuzzy/stripped match? For now, exact match.
                return {"success": False, "error": "Text to replace not found in file"}
            
            new_content = content.replace(old_text, new_text)
            
            with open(path, 'w') as f:
                f.write(new_content)
                
            return {"success": True, "action": "edit_file", "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    
    def create_file(self, path: str, content: str) -> Dict[str, Any]:
        """Create file with content."""
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)
            return {"success": True, "action": "create_file", "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def read_file(self, path: str) -> Dict[str, Any]:
        """Read file contents."""
        try:
            with open(path, 'r') as f:
                content = f.read()
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def copy_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Copy file."""
        try:
            shutil.copy2(source, destination)
            return {"success": True, "action": "copy_file", "from": source, "to": destination}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def move_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Move/rename file."""
        try:
            shutil.move(source, destination)
            return {"success": True, "action": "move_file", "from": source, "to": destination}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete file."""
        try:
            os.remove(path)
            return {"success": True, "action": "delete_file", "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_directory(self, path: str) -> Dict[str, Any]:
        """List directory contents."""
        try:
            items = os.listdir(path)
            return {"success": True, "items": items, "count": len(items)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== IMPLEMENTATION: MEDIA =====
    
    def play_spotify(self, query: str) -> Dict[str, Any]:
        """Play on Spotify (opens Spotify with search)."""
        try:
            url = f"spotify:search:{query}"
            subprocess.Popen(["xdg-open", url])
            return {"success": True, "action": "play_spotify", "query": query}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def media_control(self, action: str) -> Dict[str, Any]:
        """Control media playback in YouTube/browser via keyboard shortcuts.
        Uses xdotool to send keys to the active Chrome/browser window."""
        try:
            # Map actions to YouTube keyboard shortcuts
            key_map = {
                "play": "k",        # 'k' = YouTube play/pause (works regardless of focus)
                "pause": "k",       # 'space' scrolls page if focus isn't on player
                "play-pause": "k",
                "next": "shift+n",
                "previous": "shift+p",
                "stop": "k",
                "fullscreen": "f",
                "mute": "m",
                "volume-up": "Up",
                "volume-down": "Down",
                "forward": "Right",
                "rewind": "Left",
            }
            if action not in key_map:
                return {"success": False, "error": f"Invalid action. Use: {list(key_map.keys())}"}

            key = key_map[action]

            # Save current window to restore focus later
            try:
                active_win = subprocess.run(
                    ["xdotool", "getactivewindow"],
                    capture_output=True, text=True, timeout=3
                ).stdout.strip()
            except Exception:
                active_win = None

            # Find YouTube window — try multiple strategies
            window_id = None

            # Strategy 1: search by window name containing "YouTube"
            find_result = subprocess.run(
                ["xdotool", "search", "--name", "YouTube"],
                capture_output=True, text=True, timeout=5
            )
            wids = [w.strip() for w in find_result.stdout.strip().split('\n') if w.strip()]

            if wids:
                window_id = wids[0]
            else:
                # Strategy 2: Try searching for browser windows
                for browser in ["Firefox", "Chromium", "Chrome", "Brave"]:
                    find_b = subprocess.run(
                        ["xdotool", "search", "--name", browser],
                        capture_output=True, text=True, timeout=3
                    )
                    bids = [w.strip() for w in find_b.stdout.strip().split('\n') if w.strip()]
                    if bids:
                        window_id = bids[0]
                        break

            if window_id:
                import time

                # Activate and focus the window
                subprocess.run(["xdotool", "windowactivate", "--sync", window_id], timeout=3)
                time.sleep(0.3)
                subprocess.run(["xdotool", "windowfocus", "--sync", window_id], timeout=3)
                time.sleep(0.2)

                # For play/pause/stop, DON'T click the video area (clicking = play/pause toggle)
                # Only click for other actions like next/previous/mute to ensure player focus
                is_playback_toggle = action in ("play", "pause", "play-pause", "stop")

                if not is_playback_toggle:
                    try:
                        geom = subprocess.run(
                            ["xdotool", "getwindowgeometry", window_id],
                            capture_output=True, text=True, timeout=3
                        )
                        import re
                        geo_match = re.search(r'Geometry:\s*(\d+)x(\d+)', geom.stdout)
                        if geo_match:
                            w, h = int(geo_match.group(1)), int(geo_match.group(2))
                            click_x, click_y = w // 2, h // 3
                            subprocess.run(
                                ["xdotool", "mousemove", "--window", window_id,
                                 str(click_x), str(click_y), "click", "1"],
                                timeout=3
                            )
                            time.sleep(0.2)
                    except Exception:
                        pass

                # Send the keyboard shortcut
                subprocess.run(["xdotool", "key", "--window", window_id, key], timeout=3)

                # Restore focus to ARIA window
                if active_win:
                    time.sleep(0.3)
                    try:
                        subprocess.run(["xdotool", "windowactivate", active_win], timeout=2)
                    except Exception:
                        pass

                return {"success": True, "action": "media_control", "command": action}
            else:
                return {"success": False, "error": "No browser window found. Play something first."}

        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ===== TOOL EXECUTION =====
    
    def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a tool by name with given arguments."""
        if not hasattr(self, tool_name):
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        try:
            method = getattr(self, tool_name)
            # Inspect method signature to filter kwargs
            import inspect
            sig = inspect.signature(method)
            valid_params = sig.parameters.keys()
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
            
            return method(**filtered_kwargs)
        except TypeError as e:
            return {"success": False, "error": f"Invalid arguments: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Global instance
tools = AutomationTools()


if __name__ == "__main__":
    # Test some tools
    print("Testing AutomationTools...")
    
    # Print available tools
    print("\n" + tools.get_tools_prompt())
    
    # Test notification
    result = tools.notify("Test", "ARIA automation tools loaded!")
    print(f"\nNotification: {result}")
    
    # Test list directory
    result = tools.list_directory("/tmp")
    print(f"\nList /tmp: {result['count']} items")
