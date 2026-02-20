"""
ARIA Brain - DeepSeek Cloud Edition
Uses deepseek-v3.1:671b-cloud via Ollama with FULL context awareness:
- DOM tree from browser
- Available UI elements with aria-labels
- CDP/Playwright integration
- Complete state awareness for intelligent decision making
"""

import requests
import json
import os
import sys
import subprocess
import asyncio

# Add project to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from src.automation_tools import AutomationTools

class LocalBrain:
    """
    DeepSeek-powered brain with full DOM/CDP context awareness.
    Uses the 671B cloud model for superior reasoning and decision making.
    """
    
    def __init__(self, 
                 vision_model="deepseek-v3.1:671b-cloud", 
                 action_model="deepseek-v3.1:671b-cloud", 
                 api_url="http://localhost:11434/api/chat",
                 gpu_layers=35, 
                 ctx_size=32000):  # Larger context for DOM
        
        self.vision_model = vision_model
        self.action_model = action_model
        self.api_url = api_url
        self.gpu_layers = gpu_layers
        self.ctx_size = ctx_size
        
        # Initialize Automation Tools
        self.tools = AutomationTools()
        
        # Lazy load vision components
        self.eyes = None
        self._eyes_initialized = False
        
        # Conversation history for multi-step reasoning
        self.conversation_history = []
        
        print(f"[*] LocalBrain initialized (DeepSeek Cloud Edition)")
        print(f"    - Model: {self.action_model}")
        print(f"    - Tools: {len(self.tools.tools_registry)} available")
        print(f"    - Context: {self.ctx_size} tokens (extended for DOM)")
        
        # Load muscle memory
        self.memory = {}
        try:
            with open("training_data/manual_dataset.jsonl", "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        key = entry["instruction"].lower().strip()
                        self.memory[key] = json.loads(entry["output"])
                    except: pass
            print(f"    - Memory: {len(self.memory)} learned behaviors")
        except FileNotFoundError:
            print("    - Memory: No dataset found")
    
    def get_browser_state(self) -> dict:
        """Get complete browser state using Playwright/CDP."""
        state = {
            "connected": False,
            "url": "",
            "title": "",
            "elements": [],
            "error": None
        }
        
        try:
            # Use subprocess to run async Playwright code
            script = '''
import asyncio
import json
from playwright.async_api import async_playwright

async def get_state():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            
            # Find main page (not workers)
            page = None
            for pg in context.pages:
                title = await pg.title()
                if "whatsapp" in title.lower() or not title.startswith("WA"):
                    page = pg
                    break
            
            if not page and context.pages:
                page = context.pages[0]
            
            if not page:
                print(json.dumps({"connected": False, "error": "No pages"}))
                return
            
            url = page.url
            title = await page.title()
            
            # Get all interactive elements with aria-labels
            elements = []
            clickable = await page.query_selector_all("[aria-label], button, [role='button'], [data-icon]")
            for el in clickable[:50]:  # Limit to 50 elements
                try:
                    label = await el.get_attribute("aria-label")
                    icon = await el.get_attribute("data-icon")
                    role = await el.get_attribute("role")
                    text = (await el.inner_text())[:50] if await el.inner_text() else ""
                    if label or icon:
                        elements.append({
                            "label": label,
                            "icon": icon,
                            "role": role,
                            "text": text[:30] if text else ""
                        })
                except:
                    pass
            
            print(json.dumps({
                "connected": True,
                "url": url,
                "title": title,
                "elements": elements
            }))
            
            await browser.close()
    except Exception as e:
        print(json.dumps({"connected": False, "error": str(e)}))

asyncio.run(get_state())
'''
            result = subprocess.run(
                ["python3", "-c", script],
                capture_output=True, text=True, timeout=15,
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/.."
            )
            
            if result.stdout.strip():
                state = json.loads(result.stdout.strip())
        except Exception as e:
            state["error"] = str(e)
        
        return state
    
    def execute_cdp_action(self, action: str, target: str, text: str = "") -> dict:
        """Execute a CDP action (click, type, key) via the cdp_click.py tool."""
        try:
            if action == "type" and text:
                # For type, we may need to click first then type
                args = ["python3", "src/tools/cdp_click.py", "type", text]
            elif action == "key":
                args = ["python3", "src/tools/cdp_click.py", "key", target]
            else:
                args = ["python3", "src/tools/cdp_click.py", "click", target]
            
            result = subprocess.run(
                args,
                capture_output=True, text=True, timeout=15,
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/.."
            )
            
            if result.stdout.strip():
                return json.loads(result.stdout.strip())
            return {"success": False, "error": result.stderr or "No output"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt with all capabilities."""
        tools_list = "\n".join([
            f"- {name}: {info['description']}" 
            for name, info in self.tools.tools_registry.items()
        ])
        
        return f"""You are ARIA, a powerful AI assistant that can fully control the computer.
You have complete access to the browser state, DOM, and all automation tools.

=== WHATSAPP (via bridge on localhost:3001 — use THESE, not the whatsapp_send tool) ===
Send a message (use contact NAME, not phone number):
  {{"action": "send_message", "recipient": "<contact name>", "message": "<text>"}}
Send a file:
  {{"action": "send_file", "recipient": "<contact name>", "file_path": "<absolute path>"}}
Send a GIF:
  {{"action": "send_gif", "recipient": "<contact name>", "query": "<gif search term>"}}
Send a sticker (from image file):
  {{"action": "send_sticker", "recipient": "<contact name>", "file_path": "<image path>"}}
Read WhatsApp messages:
  {{"action": "read_whatsapp"}}

=== SYSTEM ACTIONS ===
Run shell command:
  {{"action": "shell", "command": "<command>"}}
Open application:
  {{"action": "launch", "app": "<app_name>"}}
Set wallpaper:
  {{"action": "wallpaper", "query": "<search term>"}}

=== SYSTEM TOOLS (API/Shell based — use via "tool" action) ===
{tools_list}

=== GUI ACTIONS (Browser/Desktop automation) ===
- click: Click on any element. Use the aria-label from the DOM state.
  Format: {{"action": "click", "target": "<aria-label or description>"}}

- type: Type text into focused element or specified target.
  Format: {{"action": "type", "text": "<text to type>", "target": "<optional target>"}}

- key: Press keyboard key/shortcut.
  Format: {{"action": "key", "keys": "<key like Enter, Escape, Tab>"}}

- browse: Open a URL in the browser.
  Format: {{"action": "browse", "url": "<url>"}}

- scroll: Scroll the page.
  Format: {{"action": "scroll", "direction": "up|down"}}

=== RESPONSE FORMAT ===
ALWAYS respond with valid JSON. Examples:
- {{"action": "send_message", "recipient": "Mom", "message": "hello"}}
- {{"action": "click", "target": "Menu"}}
- {{"action": "type", "text": "Shiva Jio", "target": "search"}}
- {{"action": "shell", "command": "ls -la ~/Downloads"}}
- {{"action": "browse", "url": "https://www.google.com/search?q=cat+images"}}
- {{"action": "tool", "tool_name": "set_volume", "tool_args": {{"level": 50}}}}
- {{"action": "done", "summary": "Task completed successfully"}}

=== RULES ===
- For WhatsApp messaging: ALWAYS use send_message/send_file/send_gif (NOT whatsapp_send tool)
- For shell operations: use "shell" action
- For registered tools (volume, email, weather, etc): use "tool" action
- Web search / Google search / "search for X": use "browse" with Google URL (https://www.google.com/search?q=...)
- YouTube: ONLY use youtube_search tool when user explicitly says "youtube" or "play video"
- ALWAYS check the BROWSER STATE first for GUI tasks
- Use exact aria-labels from the element list when clicking
- Handle failures gracefully
"""

    def execute_multi_step(self, goal: str, max_steps: int = 15, current_window: str = "", history: list = None) -> dict:
        """
        Execute a multi-step task with FULL state awareness.
        Uses DeepSeek 671B for superior reasoning.
        """
        print(f"[*] Multi-step execution (DeepSeek Cloud): '{goal}'")
        
        # Check muscle memory first
        if goal.lower().strip() in self.memory:
            cached = self.memory[goal.lower().strip()]
            print(f"    [Memory Hit]: {cached}")
            return {"success": True, "action": "done", "summary": "From memory", "decision": cached}
        
        step_results = []
        history = history or []
        
        for step in range(max_steps):
            print(f"\n  [Step {step + 1}/{max_steps}]")
            
            # Get LIVE browser state
            print("    > Getting browser state...")
            browser_state = self.get_browser_state()
            
            # Format element list for the prompt
            if browser_state.get("connected"):
                elements_text = "\n".join([
                    f"    - {el.get('label', el.get('icon', 'unknown'))}" 
                    for el in browser_state.get("elements", [])[:30]
                ])
                state_context = f"""
=== CURRENT BROWSER STATE ===
URL: {browser_state.get('url', 'unknown')}
Title: {browser_state.get('title', 'unknown')}
Window: {current_window}

CLICKABLE ELEMENTS (use these exact labels for clicking):
{elements_text}
"""
            else:
                state_context = f"""
=== BROWSER STATE ===
Not connected to browser. Window: {current_window}
If you need to use the browser, use "browse" action first to open a URL.
"""
            
            # Build context with history
            history_text = ""
            if history:
                history_text = f"\n\nPREVIOUS ACTIONS:\n" + "\n".join(f"- {h}" for h in history[-5:])
            if step_results:
                history_text += f"\n\nTHIS SESSION:\n" + "\n".join(
                    f"- {r.get('action', 'unknown')}: {r.get('result', {}).get('success', 'unknown')}" 
                    for r in step_results[-3:]
                )
            
            # Build messages
            messages = [
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": f"""TASK: {goal}
{state_context}
{history_text}

What is the NEXT ACTION to take? Remember:
1. Analyze the current browser state
2. Pick the most appropriate action based on what elements are visible
3. Respond with ONLY valid JSON

Your response:"""}
            ]
            
            # Call DeepSeek via Ollama
            print("    > Thinking (DeepSeek 671B)...")
            payload = {
                "model": self.action_model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,  # Low temperature for precision
                    "num_ctx": self.ctx_size
                }
            }
            
            try:
                response = requests.post(self.api_url, json=payload, timeout=120)
                response.raise_for_status()
                content = response.json()["message"]["content"]
                print(f"    Response: {content[:300]}...")
                
                # Parse response
                try:
                    # Strip and clean the content
                    content = content.strip()
                    decision = json.loads(content)
                except json.JSONDecodeError:
                    # Try to extract JSON from response - handle multi-line and nested
                    import re
                    # Find JSON object with potential nested braces
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
                    if json_match:
                        try:
                            decision = json.loads(json_match.group())
                        except json.JSONDecodeError:
                            # Last resort - try to find simpler pattern
                            simple_match = re.search(r'\{"action"\s*:\s*"[^"]+"\s*[,}]', content)
                            if simple_match:
                                # Extract just the action and try to construct minimal JSON
                                action_match = re.search(r'"action"\s*:\s*"([^"]+)"', content)
                                if action_match:
                                    decision = {"action": action_match.group(1)}
                                else:
                                    print(f"    [!] Invalid JSON, retrying...")
                                    history.append("Invalid response, retrying")
                                    continue
                            else:
                                print(f"    [!] Invalid JSON, retrying...")
                                history.append("Invalid response, retrying")
                                continue
                    else:
                        print(f"    [!] No JSON found in response, retrying...")
                        history.append("Invalid response, retrying")
                        continue
                
                # Normalize the decision to handle varied formats
                # Handle nested structures like {"thoughts": "...", "action": {...}} 
                if isinstance(decision.get("action"), dict):
                    # Flatten nested action
                    nested_action = decision["action"]
                    decision = {**decision, **nested_action}
                
                # Handle alternative key names
                if "target" not in decision and "label" in decision:
                    decision["target"] = decision["label"]
                if "target" not in decision and decision.get("action") == "click":
                    # Try to find target in any key
                    for key in ["target_description", "element", "selector", "name"]:
                        if key in decision:
                            decision["target"] = decision[key]
                            break
                
                # Handle shorthand formats like {"click": "Menu"}
                shorthand_actions = ["click", "type", "browse", "key", "scroll"]
                for act in shorthand_actions:
                    if act in decision and "action" not in decision:
                        decision["action"] = act
                        if act == "click":
                            decision["target"] = decision[act]
                        elif act == "type":
                            decision["text"] = decision[act]
                        elif act == "browse":
                            decision["url"] = decision[act]
                        break
                
                # Ensure action is a string
                action_raw = decision.get("action", "")
                if isinstance(action_raw, dict):
                    action_type = ""  # Invalid nested structure
                else:
                    action_type = str(action_raw).lower().strip()
                
                # Record step
                step_result = {"action": action_type, "decision": decision, "result": None}
                
                # Handle completion
                if action_type == "done":
                    summary = decision.get("summary", "Task completed")
                    print(f"  [✓] Task complete: {summary}")
                    return {
                        "success": True,
                        "action": "done",
                        "summary": summary,
                        "steps": step_results
                    }
                
                # Handle tool calls
                if action_type == "tool":
                    tool_name = decision.get("tool_name", "")
                    tool_args = decision.get("tool_args", {})
                    print(f"    [Tool] {tool_name}({tool_args})")
                    
                    result = self.tools.execute(tool_name, **tool_args)
                    step_result["result"] = result
                    step_results.append(step_result)
                    
                    print(f"    [Result] {str(result)[:150]}...")
                    history.append(f"Tool '{tool_name}': {'success' if result.get('success') else 'failed'}")
                    continue
                
                # Handle GUI actions
                if action_type == "click":
                    target = decision.get("target", decision.get("target_description", ""))
                    print(f"    [Click] {target}")
                    
                    result = self.execute_cdp_action("click", target)
                    step_result["result"] = result
                    step_results.append(step_result)
                    
                    if result.get("success"):
                        history.append(f"Clicked '{target}'")
                        print(f"    [✓] Clicked successfully")
                    else:
                        history.append(f"Click failed: {target}")
                        print(f"    [!] Click failed: {result.get('error')}")
                    
                    import time
                    time.sleep(1.5)  # Wait for UI update
                    continue
                
                if action_type == "type":
                    text = decision.get("text", "")
                    target = decision.get("target", "")
                    print(f"    [Type] '{text}' into '{target}'")
                    
                    # Click target first if specified
                    if target:
                        click_result = self.execute_cdp_action("click", target)
                        if not click_result.get("success"):
                            print(f"    [!] Could not focus: {target}")
                    
                    # Type text using CDP
                    result = self.execute_cdp_action("type", "", text)
                    step_result["result"] = result
                    step_results.append(step_result)
                    
                    history.append(f"Typed '{text[:20]}...'")
                    import time
                    time.sleep(1)
                    continue
                
                if action_type == "key":
                    keys = decision.get("keys", decision.get("key", ""))
                    print(f"    [Key] {keys}")
                    
                    result = self.execute_cdp_action("key", keys)
                    step_result["result"] = result
                    step_results.append(step_result)
                    
                    history.append(f"Pressed '{keys}'")
                    import time
                    time.sleep(0.5)
                    continue
                
                if action_type == "browse":
                    url = decision.get("url", "")
                    print(f"    [Browse] {url}")
                    
                    # Return browse action for main.py to handle
                    return {
                        "success": True,
                        "action": "browse",
                        "decision": decision,
                        "steps": step_results,
                        "needs_gui": True
                    }
                
                if action_type == "scroll":
                    direction = decision.get("direction", "down")
                    print(f"    [Scroll] {direction}")
                    # Implement scroll via CDP if needed
                    history.append(f"Scrolled {direction}")
                    continue
                
                # Handle WhatsApp bridge actions
                if action_type == "send_message" or action_type == "send_whatsapp":
                    recipient = decision.get("recipient", decision.get("contact", ""))
                    msg = decision.get("message", "")
                    print(f"    [WhatsApp] Sending '{msg}' to '{recipient}'...")
                    try:
                        payload = {"searchName": recipient, "message": msg}
                        r = requests.post("http://localhost:3001/send", json=payload, timeout=30)
                        data = r.json()
                        step_result["result"] = data
                        step_results.append(step_result)
                        if data.get("success"):
                            print(f"    [✓] Message sent to {recipient}")
                            history.append(f"Sent '{msg}' to {recipient}")
                            return {"success": True, "action": "done", "summary": f"Sent '{msg}' to {recipient}", "steps": step_results}
                        else:
                            history.append(f"WhatsApp failed: {data.get('error')}")
                    except Exception as e:
                        history.append(f"WhatsApp error: {e}")
                    continue
                
                if action_type == "send_file":
                    recipient = decision.get("recipient", decision.get("contact", ""))
                    file_path = decision.get("file_path", decision.get("path", ""))
                    caption = decision.get("caption", decision.get("message", ""))
                    print(f"    [WhatsApp] Sending file '{file_path}' to '{recipient}'...")
                    try:
                        payload = {"searchName": recipient, "mediaPath": file_path}
                        if caption:
                            payload["message"] = caption
                        r = requests.post("http://localhost:3001/send", json=payload, timeout=60)
                        data = r.json()
                        step_result["result"] = data
                        step_results.append(step_result)
                        if data.get("success"):
                            print(f"    [✓] File sent to {recipient}")
                            return {"success": True, "action": "done", "summary": f"Sent file to {recipient}", "steps": step_results}
                        else:
                            history.append(f"WhatsApp file failed: {data.get('error')}")
                    except Exception as e:
                        history.append(f"WhatsApp error: {e}")
                    continue
                
                if action_type == "send_gif":
                    recipient = decision.get("recipient", decision.get("contact", ""))
                    query = decision.get("query", "funny")
                    print(f"    [WhatsApp] Sending '{query}' GIF to '{recipient}'...")
                    try:
                        payload = {"searchName": recipient, "query": query}
                        r = requests.post("http://localhost:3001/send-gif", json=payload, timeout=30)
                        data = r.json()
                        step_result["result"] = data
                        step_results.append(step_result)
                        if data.get("success"):
                            print(f"    [✓] GIF sent to {recipient}")
                            return {"success": True, "action": "done", "summary": f"Sent GIF to {recipient}", "steps": step_results}
                        else:
                            history.append(f"WhatsApp GIF failed: {data.get('error')}")
                    except Exception as e:
                        history.append(f"WhatsApp error: {e}")
                    continue
                
                if action_type == "send_sticker":
                    recipient = decision.get("recipient", decision.get("contact", ""))
                    file_path = decision.get("file_path", decision.get("path", ""))
                    print(f"    [WhatsApp] Sending sticker '{file_path}' to '{recipient}'...")
                    try:
                        payload = {"searchName": recipient, "mediaPath": file_path, "sendAsSticker": True}
                        r = requests.post("http://localhost:3001/send", json=payload, timeout=30)
                        data = r.json()
                        step_result["result"] = data
                        step_results.append(step_result)
                        if data.get("success"):
                            print(f"    [✓] Sticker sent to {recipient}")
                            return {"success": True, "action": "done", "summary": f"Sent sticker to {recipient}", "steps": step_results}
                        else:
                            history.append(f"WhatsApp sticker failed: {data.get('error')}")
                    except Exception as e:
                        history.append(f"WhatsApp error: {e}")
                    continue
                
                if action_type == "read_whatsapp":
                    print(f"    [WhatsApp] Reading messages...")
                    try:
                        result = subprocess.run(
                            ["python3", "src/workflows/read_whatsapp.py"],
                            capture_output=True, text=True, timeout=15,
                            cwd=os.path.dirname(os.path.abspath(__file__)) + "/.."
                        )
                        output = result.stdout.strip() or "No messages."
                        step_result["result"] = {"success": True, "output": output}
                        step_results.append(step_result)
                        history.append(f"Read WhatsApp: {output[:50]}")
                    except Exception as e:
                        history.append(f"Read WhatsApp error: {e}")
                    continue
                
                if action_type == "shell":
                    command = decision.get("command", "")
                    print(f"    [Shell] {command}")
                    dangerous = ["rm -rf /", "rm -rf /*", ":(){ :|:& };:", "mkfs", "dd if="]
                    if any(d in command for d in dangerous):
                        history.append(f"Blocked dangerous: {command}")
                        continue
                    try:
                        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
                        output = result.stdout.strip() or result.stderr.strip() or "(no output)"
                        step_result["result"] = {"success": result.returncode == 0, "output": output[:200]}
                        step_results.append(step_result)
                        history.append(f"Shell '{command}': {output[:50]}")
                        return {"success": True, "action": "done", "summary": f"$ {command}\n{output[:200]}", "steps": step_results}
                    except Exception as e:
                        history.append(f"Shell error: {e}")
                    continue
                
                if action_type == "launch":
                    app = decision.get("app", "")
                    print(f"    [Launch] {app}")
                    try:
                        subprocess.Popen([app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        history.append(f"Launched {app}")
                        return {"success": True, "action": "done", "summary": f"Launched {app}", "steps": step_results}
                    except Exception as e:
                        history.append(f"Launch error: {e}")
                    continue
                
                # Unknown action
                print(f"    [?] Unknown action: {action_type}")
                history.append(f"Unknown action: {action_type}")
                
            except Exception as e:
                print(f"    [Error] {e}")
                import traceback
                traceback.print_exc()
                step_results.append({"action": "error", "error": str(e)})
                history.append(f"Error: {str(e)[:50]}")
        
        print(f"  [!] Max steps ({max_steps}) reached")
        return {
            "success": False,
            "error": "Max steps reached",
            "steps": step_results
        }
    
    def think(self, user_goal, detected_items=[], history=[], active_window="Unknown", image_base64=None, dom_tree=""):
        """
        Main thinking method - wraps execute_multi_step.
        """
        result = self.execute_multi_step(user_goal, max_steps=15, current_window=active_window, history=history)
        
        if result.get("success"):
            action = result.get("action", "")
            
            if action == "done":
                return {"action": "done", "reason": result.get("summary", "")}
            
            # Pass GUI actions through to main.py
            if result.get("needs_gui"):
                decision = result.get("decision", {})
                return {**decision, "from_brain": True}
        
        # Return last attempted action or error
        return {"action": "wait", "reason": result.get("error", "Unknown error")}
    
    def process(self, user_goal, image_path=None, history=[], active_window="Unknown"):
        """Legacy compatibility method."""
        return self.think(user_goal, [], history, active_window)


# Quick test
if __name__ == "__main__":
    brain = LocalBrain()
    
    # Test with browser state
    print("\n=== Testing Browser State ===")
    state = brain.get_browser_state()
    print(json.dumps(state, indent=2))
    
    # Test multi-step task
    print("\n=== Testing Multi-Step Execution ===")
    result = brain.execute_multi_step("click on the menu button in whatsapp")
    print(f"\nFinal Result: {json.dumps(result, indent=2)}")
