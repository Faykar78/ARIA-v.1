"""
Visual RAG Browser Agent with Gemini-style Reasoning

Uses screenshots + DOM tree for vision, chain-of-thought reasoning,
and pixel-based click targeting - exactly like Gemini's browser subagent.
"""

import asyncio
import base64
import json
import os
import requests
from typing import Optional, Dict, List, Any, Tuple
from playwright.async_api import async_playwright, Page, Browser

# Import automation tools for system-level actions
try:
    from automation_tools import AutomationTools
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False


class VisualBrowserAgent:
    """
    Enhanced browser agent with Gemini-style visual reasoning:
    - Screenshot capture for visual understanding  
    - DOM tree for semantic structure
    - Chain-of-thought reasoning
    - Pixel-based click targeting
    - System automation capabilities (files, media, notifications, etc.)
    """
    
    def __init__(
        self,
        model: str = "qwen2.5vl:3b",  # Qwen2.5-VL vision model (better than llava)
        ollama_url: str = "http://localhost:11434/api/chat",
        cdp_url: str = "http://localhost:9222",
        screenshot_dir: str = "/tmp/browser_agent"
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.cdp_url = cdp_url
        self.screenshot_dir = screenshot_dir
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.history: List[Dict] = []
        self.max_steps = 20
        self.step_count = 0
        
        # Initialize automation tools
        if AUTOMATION_AVAILABLE:
            self.tools = AutomationTools()
            print(f"[VisualBrowserAgent] Automation tools loaded: {len(self.tools.tools_registry)} tools")
        else:
            self.tools = None
        
        os.makedirs(screenshot_dir, exist_ok=True)
        
        print(f"[VisualBrowserAgent] Initialized")
        print(f"  - Vision Model: {model}")
        print(f"  - Ollama: {ollama_url}")
        print(f"  - CDP: {cdp_url}")
        print(f"  - Screenshots: {screenshot_dir}")
    
    async def connect(self) -> bool:
        """Connect to existing Chrome browser via CDP."""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.connect_over_cdp(self.cdp_url)
            
            contexts = self.browser.contexts
            if not contexts:
                print("[!] No browser contexts found")
                return False
            
            pages = contexts[0].pages
            if not pages:
                print("[!] No pages found")
                return False
            
            self.page = pages[0]
            print(f"[+] Connected to: {self.page.url}")
            return True
            
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            return False
    
    async def capture_screenshot(self) -> Tuple[str, str]:
        """
        Capture screenshot and return (file_path, base64_encoded).
        This is the VISION input - exactly like Gemini sees.
        """
        if not self.page:
            return "", ""
        
        self.step_count += 1
        filename = f"step_{self.step_count:03d}.png"
        filepath = os.path.join(self.screenshot_dir, filename)
        
        try:
            await self.page.screenshot(path=filepath, full_page=False)
            
            with open(filepath, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            
            print(f"  [Vision] Captured screenshot: {filename}")
            return filepath, b64
            
        except Exception as e:
            print(f"  [!] Screenshot failed: {e}")
            return "", ""
    
    async def get_page_info(self) -> Dict[str, Any]:
        """Get page URL and title for context."""
        if not self.page:
            return {}
        
        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "viewport": await self.page.evaluate("() => ({width: window.innerWidth, height: window.innerHeight})")
        }
    
    async def get_interactive_elements(self) -> List[Dict]:
        """
        Extract interactive elements with their bounding boxes.
        This provides GROUNDING - knowing WHERE to click.
        """
        if not self.page:
            return []
        
        try:
            elements = await self.page.evaluate("""
            () => {
                const interactive = [];
                const selectors = 'button, a, input, select, textarea, [role="button"], [onclick], [tabindex]';
                
                document.querySelectorAll(selectors).forEach((el, idx) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    
                    // Skip hidden elements
                    if (style.display === 'none' || style.visibility === 'hidden' || 
                        rect.width === 0 || rect.height === 0) {
                        return;
                    }
                    
                    // Skip elements outside viewport
                    if (rect.top > window.innerHeight || rect.bottom < 0 ||
                        rect.left > window.innerWidth || rect.right < 0) {
                        return;
                    }
                    
                    const text = el.innerText?.slice(0, 50) || 
                                 el.value?.slice(0, 50) || 
                                 el.getAttribute('aria-label') ||
                                 el.getAttribute('placeholder') ||
                                 el.getAttribute('title') || '';
                    
                    interactive.push({
                        id: idx,
                        tag: el.tagName.toLowerCase(),
                        type: el.type || el.getAttribute('role') || '',
                        text: text.trim(),
                        x: Math.round(rect.left + rect.width / 2),
                        y: Math.round(rect.top + rect.height / 2),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    });
                });
                
                return interactive.slice(0, 50);  // Limit to 50 elements
            }
            """)
            
            return elements
            
        except Exception as e:
            print(f"  [!] Element extraction failed: {e}")
            return []
    
    def find_best_element_match(self, target: str, elements: List[Dict], page_url: str = "") -> Optional[Dict]:
        """
        HYBRID APPROACH: Find the best matching DOM element for a VLM target description.
        
        Uses text similarity matching instead of trusting VLM coordinates.
        This allows VLM to reason about WHAT to click while DOM provides accurate WHERE.
        """
        if not target or not elements:
            return None
        
        target_lower = target.lower().strip()
        best_match = None
        best_score = 0
        
        # Detect account chooser page - VLM is unreliable here, override its decision
        is_account_chooser = "accountchooser" in page_url.lower()
        
        # AGGRESSIVE OVERRIDE for account chooser: find and click email element
        if is_account_chooser:
            for el in elements:
                el_text = el.get("text", "").lower()
                el_size = el.get("width", 1000) * el.get("height", 1000)
                # Look for email addresses (not in huge containers)
                if "@gmail.com" in el_text and el_size < 100000:
                    print(f"  [Override] Account chooser detected - selecting email account")
                    return el
                elif "@" in el_text and el_size < 100000 and "privacy" not in el_text and "service" not in el_text:
                    print(f"  [Override] Account chooser detected - selecting email account")
                    return el
        
        for el in elements:
            el_text = el.get("text", "").lower().strip()
            if not el_text:
                continue
            
            score = 0
            el_size = el.get("width", 1000) * el.get("height", 1000)
            
            # HEAVY PENALTY FOR LARGE CONTAINERS (they're never the right target)
            if el_size > 100000:  # Larger than ~316x316
                continue  # Skip entirely - these are always containers
            
            # Exact match
            if target_lower == el_text:
                score = 100
            # Target fully contained in element
            elif target_lower in el_text:
                score = 80
            # Element text fully contained in target
            elif el_text in target_lower:
                score = 70
            # Any word match (for emails, names, etc.)
            else:
                target_words = set(target_lower.replace("@", " ").replace(".", " ").split())
                el_words = set(el_text.replace("@", " ").replace(".", " ").split())
                common = target_words & el_words
                if common:
                    score = 40 + (len(common) * 10)
            
            # Prefer smaller elements (more specific, not containers)
            if score > 0:
                if el_size < 10000:  # Smaller than ~100x100 (likely a button)
                    score += 15
                elif el_size < 50000:  # Smaller than ~225x225
                    score += 5
            
            if score > best_score:
                best_score = score
                best_match = el
        
        if best_match:
            print(f"  [Match] '{target[:30]}' → '{best_match.get('text', '')[:30]}' at ({best_match['x']}, {best_match['y']}) [score={best_score}]")
        
        return best_match
    
    def heuristic_action(self, goal: str, elements: List[Dict], page_info: Dict) -> Optional[Dict]:
        """
        Fast heuristic fallback - match goal keywords to elements WITHOUT calling VLM.
        This is a fallback when the model is too slow.
        """
        goal_lower = goal.lower()
        url = page_info.get("url", "")
        
        # Check if there's still a "Sign in" button visible
        has_signin_button = any("sign in" in el.get("text", "").lower() for el in elements)
        
        # If on chat page AND no sign in button, user is actually logged in
        if "/chat" in url and not has_signin_button:
            return {"action": "done", "success": True, "reasoning": "On chat page with no Sign in button - logged in"}
        
        # If on chat page but Sign in button exists, click it (guest access, need to login)
        if "/chat" in url and has_signin_button:
            # First check for OAuth buttons (modal is open)
            for el in elements:
                el_text = el.get("text", "").lower()
                if "continue with google" in el_text or el_text == "google":
                    return {
                        "action": "click",
                        "target": el.get("text", ""),
                        "x": el.get("x"),
                        "y": el.get("y"),
                        "reasoning": f"Found 'Continue with Google' button - clicking to login"
                    }
            
            # Then click Sign in to open the modal
            for el in elements:
                if "sign in" in el.get("text", "").lower():
                    return {
                        "action": "click",
                        "target": el.get("text", ""),
                        "x": el.get("x"),
                        "y": el.get("y"),
                        "reasoning": f"On chat page but not logged in - clicking 'Sign in' button"
                    }
        
        # Build keyword-to-action mappings
        keyword_actions = [
            (["sign in", "login", "log in"], ["sign in", "login", "log in"]),
            (["continue with google", "google"], ["continue with google", "google"]),
            (["start now", "get started"], ["start now", "get started"]),
            (["next", "continue"], ["next", "continue"]),
            (["submit", "confirm"], ["submit", "confirm", "ok"]),
        ]
        
        for goal_keywords, element_keywords in keyword_actions:
            if any(kw in goal_lower for kw in goal_keywords):
                for el in elements:
                    el_text = el.get("text", "").lower()
                    if any(kw in el_text for kw in element_keywords):
                        return {
                            "action": "click",
                            "target": el.get("text", ""),
                            "x": el.get("x"),
                            "y": el.get("y"),
                            "reasoning": f"Heuristic match: '{el.get('text')}' matches goal"
                        }
        
        # If goal mentions verify/check and we're on use.ai homepage, click Sign in
        if any(kw in goal_lower for kw in ["verify", "check", "login", "sign"]):
            for el in elements:
                if "sign in" in el.get("text", "").lower():
                    return {
                        "action": "click",
                        "target": el.get("text", ""),
                        "x": el.get("x"),
                        "y": el.get("y"),
                        "reasoning": f"Heuristic: clicking 'Sign in' to verify login"
                    }
        
        return None  # No heuristic match
    
    async def reason_and_act(self, goal: str, screenshot_b64: str, 
                              page_info: Dict, elements: List[Dict]) -> Dict[str, Any]:
        """
        Chain-of-thought reasoning with vision - exactly like Gemini.
        
        The model sees:
        1. The screenshot (visual understanding)
        2. Interactive elements with coordinates (grounding)
        3. History of past actions (context)
        4. The goal (intent)
        
        And outputs a reasoned action with coordinates.
        """
        
        # Format history
        history_str = ""
        for h in self.history[-5:]:
            history_str += f"- Action: {h.get('action')} | Target: {h.get('target', 'N/A')} | Result: {h.get('result', 'done')}\n"
        
        # Format elements as a simple list
        elements_str = ""
        for el in elements[:30]:
            elements_str += f"[{el['id']}] {el['tag']} \"{el['text'][:30]}\" at ({el['x']}, {el['y']}) size:{el['width']}x{el['height']}\n"
        
        # Log elements for debugging
        if elements:
            print(f"  [Elements] {elements_str[:500]}...")
        
        # The exact reasoning prompt I use
        tools_prompt = ""
        if self.tools:
            tools_prompt = """

SYSTEM TOOLS (for non-browser actions):
You can also use these tools for system automation:
- youtube_search(query): Search and play YouTube video
- youtube_download(url, audio_only): Download video/audio
- whatsapp_send(phone_number, message): Send WhatsApp message
- email_send(to, subject, body): Send email
- notify(title, message): Show desktop notification
- open_app(app_name): Open an application
- run_command(command): Run shell command (bash)
- create/read/edit/delete_file: File operations
- play_spotify(query): Play music on Spotify
- media_control(action): Control media (play/pause/next)
- set_volume/brightness(level): Control system
- github_ops(op, repo): GitHub actions (issues, PRs)
- discord_send(url, content): Send Discord webhook
- weather_check(location): Check weather
- list/kill_process: Manage running apps
- manage_tmux(action, session): Manage terminal sessions
- read_pdf(path): Extract text from PDFs
- screenshot(filename): Take screenshot

To use a tool, set action="tool" and include:
  "tool_name": "tool_name_here",
  "tool_args": {"arg1": "value1", ...}
"""
        
        system_prompt = f"""You are a browser automation agent with VISION. You can SEE the screenshot.

YOUR TASK: Analyze the screenshot, recognize the PAGE STATE, and decide the appropriate action.

STEP 1 - RECOGNIZE PAGE STATE:
Look at the screenshot and identify which state the page is in:
- HOMEPAGE: Website landing page with "Sign in" or "Get Started" buttons
- LOGIN_MODAL: Popup with OAuth options like "Continue with Google", "Continue with Facebook"
- ACCOUNT_CHOOSER: Google page showing "Choose an account" with email addresses listed (e.g., user@gmail.com)
- EMAIL_INPUT: Google page with "Email or phone" input field
- PASSWORD_INPUT: Google page with "Enter your password" input field
- LOGGED_IN: Main app interface (e.g., chat page with message input)
- GENERAL: Any other page state

STEP 2 - CHOOSE ACTION TYPE:
- For browser interactions: click, type, scroll, wait, done
- For system actions: tool (youtube, files, notifications, etc.)
{tools_prompt}
STEP 3 - STATE-SPECIFIC BROWSER ACTIONS:
- HOMEPAGE → Click "Sign in" button
- LOGIN_MODAL → Click "Continue with Google" button
- ACCOUNT_CHOOSER → Click the EMAIL ADDRESS (e.g., "user@gmail.com"), NOT the header text!
- EMAIL_INPUT → Type email in the input field, then click "Next"
- PASSWORD_INPUT → Type password, then click "Next"
- LOGGED_IN → Return done with success=true

OUTPUT FORMAT (JSON only):
{{
  "page_state": "HOMEPAGE|LOGIN_MODAL|ACCOUNT_CHOOSER|...",
  "observation": "I see [describe the UI]...",
  "reasoning": "Since this is [state], I should [action]...",
  "action": "click|type|scroll|wait|done|tool",
  "target": "EXACT ELEMENT TEXT to click",
  "text": "text to type (if action is type)",
  "tool_name": "tool name (if action is tool)",
  "tool_args": {{"arg": "value"}} (if action is tool),
  "success": true/false (only for done action)
}}

CRITICAL: On ACCOUNT_CHOOSER, the target MUST be the email like "user@gmail.com", NOT "Sign in with Google" or "Choose an account"."""

        user_prompt = f"""GOAL: {goal}

CURRENT PAGE:
- URL: {page_info.get('url', 'unknown')}
- Title: {page_info.get('title', 'unknown')}
- Viewport: {page_info.get('viewport', {})}

ACTION HISTORY:
{history_str if history_str else "(no actions yet)"}

INTERACTIVE ELEMENTS (id, tag, text, coordinates):
{elements_str if elements_str else "(no elements detected)"}

Look at the screenshot and decide the next action. Think step by step.
Return ONLY valid JSON."""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user", 
                    "content": user_prompt,
                    "images": [screenshot_b64] if screenshot_b64 else []
                }
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_ctx": 4096
            }
        }
        
        try:
            print("  [Reasoning] Thinking with vision...")
            response = requests.post(self.ollama_url, json=payload, timeout=120)
            response.raise_for_status()
            content = response.json()["message"]["content"]
            
            # Parse and display reasoning
            parsed = json.loads(content)
            
            if parsed.get("observation"):
                print(f"  [Observe] {parsed['observation'][:100]}...")
            if parsed.get("reasoning"):
                print(f"  [Reason] {parsed['reasoning'][:100]}...")
            
            return parsed
            
        except json.JSONDecodeError as e:
            print(f"  [!] JSON parse error: {e}")
            return {"action": "wait", "reasoning": "Parse error"}
        except Exception as e:
            print(f"  [!] Vision API error: {e}")
            return {"action": "wait", "reasoning": str(e)}
    
    async def execute_action(self, decision: Dict[str, Any]) -> str:
        """Execute the decided action using Playwright."""
        if not self.page:
            return "no_page"
        
        action = decision.get("action", "").lower()
        target = decision.get("target", "")
        x = decision.get("x", 0)
        y = decision.get("y", 0)
        
        try:
            if action == "click":
                print(f"  [Execute] Click at ({x}, {y}) - {target}")
                
                if x and y:
                    # Pixel-based click - most accurate
                    await self.page.mouse.click(x, y)
                else:
                    # Fallback to text-based click
                    await self.page.get_by_text(target, exact=False).first.click(timeout=5000)
                
                await asyncio.sleep(1.5)  # Wait for UI response
                return "clicked"
            
            elif action == "type":
                text = decision.get("text", "")
                print(f"  [Execute] Type '{text}' at ({x}, {y})")
                
                if x and y:
                    await self.page.mouse.click(x, y)
                    await asyncio.sleep(0.3)
                
                await self.page.keyboard.type(text, delay=50)
                return "typed"
            
            elif action == "scroll":
                direction = decision.get("direction", "down")
                delta = 400 if direction == "down" else -400
                print(f"  [Execute] Scroll {direction}")
                await self.page.mouse.wheel(0, delta)
                await asyncio.sleep(0.5)
                return "scrolled"
            
            elif action == "wait":
                seconds = decision.get("seconds", 2)
                print(f"  [Execute] Wait {seconds}s")
                await asyncio.sleep(seconds)
                return "waited"
            
            elif action == "navigate":
                url = decision.get("url", "")
                print(f"  [Execute] Navigate to {url}")
                if not url.startswith("http"):
                    url = "https://" + url
                await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                return "navigated"
            
            elif action == "done":
                success = decision.get("success", False)
                print(f"  [Execute] Done - {'SUCCESS' if success else 'FAILED'}")
                return "done"
            
            elif action == "tool":
                # Execute automation tool
                tool_name = decision.get("tool_name", "")
                tool_args = decision.get("tool_args", {})
                
                if not self.tools:
                    print(f"  [!] Automation tools not available")
                    return "error: tools not available"
                
                if not tool_name:
                    print(f"  [!] No tool name specified")
                    return "error: no tool name"
                
                print(f"  [Execute] Tool: {tool_name}({tool_args})")
                result = self.tools.execute(tool_name, **tool_args)
                
                if result.get("success"):
                    print(f"  [Tool] Success: {result}")
                    return f"tool:{tool_name}"
                else:
                    print(f"  [Tool] Failed: {result.get('error', 'unknown error')}")
                    return f"error: {result.get('error', 'unknown')}"
            
            else:
                print(f"  [!] Unknown action: {action}")
                return "unknown"
                
        except Exception as e:
            print(f"  [!] Execution error: {e}")
            return f"error: {e}"
    
    async def run(self, goal: str) -> bool:
        """
        Main agent loop with visual reasoning.
        This mimics exactly how Gemini's browser subagent works.
        """
        print(f"\n{'='*60}")
        print(f"[VisualBrowserAgent] Goal: {goal}")
        print(f"{'='*60}\n")
        
        if not self.page:
            if not await self.connect():
                return False
        
        for step in range(self.max_steps):
            print(f"\n--- Step {step + 1}/{self.max_steps} ---")
            
            # 1. CAPTURE - Take screenshot (vision input)
            screenshot_path, screenshot_b64 = await self.capture_screenshot()
            
            # 2. CONTEXT - Get page info and elements
            page_info = await self.get_page_info()
            elements = await self.get_interactive_elements()
            
            print(f"  [Context] {page_info.get('url', 'unknown')}")
            print(f"  [Context] Found {len(elements)} interactive elements")
            
            # VLM REASONING - Chain of thought with vision
            decision = await self.reason_and_act(goal, screenshot_b64, page_info, elements)
            
            # HYBRID APPROACH: Use DOM matcher to find correct element coordinates
            if decision.get("action") == "click" and decision.get("target"):
                matched_element = self.find_best_element_match(decision["target"], elements, page_info.get("url", ""))
                if matched_element:
                    # Override VLM coordinates with matched element's coordinates
                    decision["x"] = matched_element["x"]
                    decision["y"] = matched_element["y"]
                    decision["matched_text"] = matched_element.get("text", "")[:30]
                else:
                    print(f"  [!] No match found for target '{decision.get('target')}'")
                    # Fall back to VLM coordinates if no match (may be wrong but try anyway)
            
            # 4. CHECK - Is goal complete?
            if decision.get("action") == "done":
                success = decision.get("success", False)
                reason = decision.get("reasoning", "")
                print(f"\n{'='*60}")
                print(f"[{'✓' if success else '✗'}] {'GOAL ACHIEVED' if success else 'GOAL FAILED'}")
                print(f"Reason: {reason}")
                print(f"{'='*60}")
                return success
            
            # 5. ACT - Execute the decision
            result = await self.execute_action(decision)
            
            # 6. RECORD - Add to history for context
            self.history.append({
                "action": decision.get("action"),
                "target": decision.get("target"),
                "x": decision.get("x"),
                "y": decision.get("y"),
                "result": result
            })
            
            # Brief pause between steps
            await asyncio.sleep(0.5)
        
        print(f"\n[!] Max steps reached without completion")
        return False
    
    async def close(self):
        """Disconnect from browser."""
        if self.browser:
            await self.browser.close()
            print("[*] Disconnected")


# === CLI Interface ===
async def main():
    import sys
    
    goal = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "login to use.ai with Google"
    
    # Use Qwen2.5-VL for vision (better than LLaVA)
    agent = VisualBrowserAgent(
        model="qwen2.5vl:3b",  # Qwen2.5-VL vision model
        screenshot_dir="/tmp/visual_agent"
    )
    
    try:
        success = await agent.run(goal)
        return 0 if success else 1
    finally:
        await agent.close()


if __name__ == "__main__":
    exit(asyncio.run(main()))
