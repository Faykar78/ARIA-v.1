"""
RAG Browser Agent with Llama + Playwright

Uses DOM tree as vision input, Llama for intelligent decision-making,
and Playwright for browser actions. Designed for login verification.
"""

import asyncio
import json
import requests
from typing import Optional, Dict, List, Any
from playwright.async_api import async_playwright, Page, Browser

class RAGBrowserAgent:
    """
    Intelligent browser agent using:
    - DOM accessibility tree as vision
    - Llama/Ollama for action decisions
    - Playwright for browser control
    """
    
    def __init__(
        self,
        model: str = "qwen2.5vl:3b",
        ollama_url: str = "http://localhost:11434/api/chat",
        cdp_url: str = "http://localhost:9222"
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.cdp_url = cdp_url
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.history: List[str] = []
        self.max_steps = 15
        
        print(f"[RAGBrowserAgent] Initialized")
        print(f"  - Model: {model}")
        print(f"  - Ollama: {ollama_url}")
        print(f"  - CDP: {cdp_url}")
    
    async def connect(self) -> bool:
        """Connect to existing Chrome browser via CDP."""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.connect_over_cdp(self.cdp_url)
            
            # Get the first context and page
            contexts = self.browser.contexts
            if not contexts:
                print("[!] No browser contexts found")
                return False
            
            pages = contexts[0].pages
            if not pages:
                print("[!] No pages found in browser")
                return False
            
            self.page = pages[0]
            print(f"[+] Connected to page: {self.page.url}")
            return True
            
        except Exception as e:
            print(f"[!] Failed to connect to browser: {e}")
            print("    Make sure Chrome is running with --remote-debugging-port=9222")
            return False
    
    async def get_dom_tree(self, max_depth: int = 8) -> Dict[str, Any]:
        """
        Extract DOM tree from current page using JavaScript evaluation.
        Returns a simplified structure suitable for LLM processing.
        """
        if not self.page:
            return {"error": "No page connected"}
        
        try:
            # JavaScript to extract semantic DOM tree
            js_code = """
            () => {
                function extractTree(element, depth = 0) {
                    if (depth > 8 || !element) return null;
                    
                    const tag = element.tagName?.toLowerCase() || '';
                    const role = element.getAttribute('role') || '';
                    const ariaLabel = element.getAttribute('aria-label') || '';
                    const text = element.innerText?.slice(0, 100) || '';
                    const placeholder = element.placeholder || '';
                    const type = element.type || '';
                    const href = element.href || '';
                    const id = element.id || '';
                    const className = element.className?.toString().slice(0, 50) || '';
                    
                    // Skip hidden elements
                    const style = window.getComputedStyle(element);
                    if (style.display === 'none' || style.visibility === 'hidden') {
                        return null;
                    }
                    
                    // Build node info
                    let node = {};
                    
                    // Determine role
                    if (role) node.role = role;
                    else if (tag === 'button' || type === 'submit') node.role = 'button';
                    else if (tag === 'a') node.role = 'link';
                    else if (tag === 'input') node.role = type || 'textbox';
                    else if (tag === 'img') node.role = 'image';
                    else if (['h1','h2','h3','h4','h5','h6'].includes(tag)) node.role = 'heading';
                    else if (tag) node.tag = tag;
                    
                    // Add name/label
                    if (ariaLabel) node.name = ariaLabel;
                    else if (placeholder) node.name = placeholder;
                    else if (tag === 'img' && element.alt) node.name = element.alt;
                    else if (text && text.length < 100 && !text.includes('\\n')) node.name = text.trim();
                    
                    // Add value for inputs
                    if (element.value && tag === 'input') node.value = element.value;
                    
                    // Add href for links
                    if (href && tag === 'a') node.href = href.slice(0, 100);
                    
                    // Add id if present
                    if (id) node.id = id;
                    
                    // Process interactive children
                    const interactiveTags = ['button', 'a', 'input', 'select', 'textarea', 'form'];
                    const children = [];
                    
                    for (const child of element.children || []) {
                        const childNode = extractTree(child, depth + 1);
                        if (childNode) {
                            children.push(childNode);
                        }
                    }
                    
                    if (children.length > 0) {
                        node.children = children;
                    }
                    
                    // Filter empty nodes
                    if (Object.keys(node).length === 0) return null;
                    if (!node.name && !node.role && !node.children) return null;
                    
                    return node;
                }
                
                return extractTree(document.body, 0);
            }
            """;
            
            tree = await self.page.evaluate(js_code)
            
            # Add page metadata
            result = {
                "url": self.page.url,
                "title": await self.page.title(),
                "tree": tree or {}
            }
            
            return result
            
        except Exception as e:
            print(f"[!] Error getting DOM tree: {e}")
            return {"error": str(e)}
    
    def _truncate_dom(self, dom: Dict, max_chars: int = 8000) -> str:
        """Convert DOM to string and truncate if needed."""
        dom_str = json.dumps(dom, indent=None)
        if len(dom_str) > max_chars:
            return dom_str[:max_chars] + "\n...(truncated)"
        return dom_str
    
    async def ask_llama(self, goal: str, dom: Dict) -> Dict[str, Any]:
        """
        Ask Llama to decide the next action based on goal and DOM state.
        Returns a structured action dictionary.
        """
        dom_str = self._truncate_dom(dom)
        history_str = "\n".join([f"- {h}" for h in self.history[-10:]])
        
        system_prompt = """You are a Browser Automation Agent. Analyze the DOM tree and decide the next action.

OUTPUT FORMAT: Return ONLY valid JSON with one of these actions:

{"action": "click", "target": "button/link name or role", "reason": "why"}
{"action": "type", "text": "text to type", "target": "input field name", "reason": "why"}
{"action": "navigate", "url": "https://...", "reason": "why"}
{"action": "wait", "seconds": 2, "reason": "waiting for..."}
{"action": "scroll", "direction": "down", "reason": "why"}
{"action": "done", "success": true/false, "reason": "goal achieved/failed because..."}

GOOGLE OAUTH LOGIN FLOW:
1. First, click "Sign in" or "Log in" button on the main page
2. Look for "Continue with Google", "Sign in with Google", or Google logo button - CLICK IT
3. On Google's page (accounts.google.com): 
   - If you see email accounts listed, click on the account to use
   - If you see "Use another account", an email input may appear - type email then click Next
   - If password is needed, type password then click Next
4. After OAuth completes, you'll be redirected back - verify login succeeded

LOGIN SUCCESS INDICATORS:
- User profile picture/avatar visible
- User name or email displayed
- Chat/dashboard interface instead of landing page
- Logout/Sign out button visible
- URL changed to /chat, /dashboard, /app, etc.

LOGIN FAILURE INDICATORS:
- Still seeing "Sign in" or "Log in" buttons
- Login form still visible
- Error messages about authentication

RULES:
1. If on accounts.google.com, you're in OAuth flow - look for account to click or credentials to enter
2. After clicking Continue with Google, WAIT for page to load before next action
3. Use "done" with success=true when you see logged-in state, success=false if stuck
4. Do NOT repeat failed actions - try alternatives or report failure"""

        user_prompt = f"""GOAL: {goal}

PAGE URL: {dom.get('url', 'unknown')}
PAGE TITLE: {dom.get('title', 'unknown')}

HISTORY:
{history_str if history_str else "(no actions yet)"}

DOM TREE (Accessibility Snapshot):
{dom_str}

What is the next action? Return ONLY JSON."""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_ctx": 4096
            }
        }
        
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=60)
            response.raise_for_status()
            content = response.json()["message"]["content"]
            print(f"  [Llama] {content[:200]}...")
            
            parsed = json.loads(content)
            return parsed
            
        except json.JSONDecodeError as e:
            print(f"  [!] Failed to parse Llama response: {e}")
            return {"action": "wait", "seconds": 1, "reason": "Parse error, retrying"}
        except Exception as e:
            print(f"  [!] Llama API error: {e}")
            return {"action": "wait", "seconds": 2, "reason": f"API error: {e}"}
    
    async def execute_action(self, action: Dict[str, Any]) -> bool:
        """
        Execute the action using Playwright.
        Returns True if action was successful.
        """
        if not self.page:
            return False
        
        action_type = action.get("action", "").lower()
        reason = action.get("reason", "")
        
        try:
            if action_type == "click":
                target = action.get("target", "")
                print(f"  [Action] Click: '{target}' - {reason}")
                
                # Try multiple selectors
                locators = [
                    self.page.get_by_role("button", name=target),
                    self.page.get_by_role("link", name=target),
                    self.page.get_by_text(target, exact=False),
                    self.page.locator(f"[aria-label*='{target}' i]"),
                ]
                
                for locator in locators:
                    try:
                        if await locator.count() > 0:
                            await locator.first.click(timeout=5000)
                            self.history.append(f"Clicked '{target}'")
                            await asyncio.sleep(1)
                            return True
                    except:
                        continue
                
                print(f"  [!] Could not find clickable element: {target}")
                return False
            
            elif action_type == "type":
                text = action.get("text", "")
                target = action.get("target", "")
                print(f"  [Action] Type: '{text}' into '{target}' - {reason}")
                
                # Find input field
                locators = [
                    self.page.get_by_role("textbox", name=target),
                    self.page.get_by_placeholder(target),
                    self.page.locator(f"input[name*='{target}' i]"),
                    self.page.locator("input:visible").first,
                ]
                
                for locator in locators:
                    try:
                        if await locator.count() > 0:
                            await locator.first.fill(text)
                            self.history.append(f"Typed '{text}' into '{target}'")
                            return True
                    except:
                        continue
                
                return False
            
            elif action_type == "navigate":
                url = action.get("url", "")
                print(f"  [Action] Navigate: {url} - {reason}")
                
                if not url.startswith("http"):
                    url = "https://" + url
                
                await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                self.history.append(f"Navigated to {url}")
                await asyncio.sleep(2)
                return True
            
            elif action_type == "wait":
                seconds = action.get("seconds", 2)
                print(f"  [Action] Wait: {seconds}s - {reason}")
                await asyncio.sleep(seconds)
                return True
            
            elif action_type == "scroll":
                direction = action.get("direction", "down")
                print(f"  [Action] Scroll: {direction} - {reason}")
                
                delta = 500 if direction == "down" else -500
                await self.page.mouse.wheel(0, delta)
                self.history.append(f"Scrolled {direction}")
                await asyncio.sleep(0.5)
                return True
            
            elif action_type == "done":
                success = action.get("success", False)
                print(f"  [Action] Done: {'SUCCESS' if success else 'FAILED'} - {reason}")
                return True
            
            else:
                print(f"  [!] Unknown action: {action_type}")
                return False
                
        except Exception as e:
            print(f"  [!] Action failed: {e}")
            return False
    
    async def verify_login(self, url: str = "use.ai") -> bool:
        """
        Navigate to URL and verify if user is logged in.
        Returns True if logged in, False otherwise.
        """
        if not self.page:
            if not await self.connect():
                return False
        
        # Navigate if not already on the page
        current_url = self.page.url.lower()
        if url.lower() not in current_url:
            print(f"[*] Navigating to {url}...")
            full_url = url if url.startswith("http") else f"https://{url}"
            await self.page.goto(full_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
        
        # Get DOM and ask Llama to verify
        dom = await self.get_dom_tree()
        
        verification_prompt = "Check if the user is logged in. Look for: user profile, avatar, dashboard, settings, logout button. If you see login/signup form, user is NOT logged in."
        
        result = await self.ask_llama(
            f"Verify if user is logged in on {url}. {verification_prompt}",
            dom
        )
        
        if result.get("action") == "done":
            return result.get("success", False)
        
        # If Llama wants to explore more, run a few steps
        return await self.run(f"verify successful login on {url}")
    
    async def run(self, goal: str) -> bool:
        """
        Main agent loop - execute actions until goal is achieved or max steps reached.
        Returns True if goal was achieved successfully.
        """
        print(f"\n{'='*60}")
        print(f"[RAGBrowserAgent] Starting: {goal}")
        print(f"{'='*60}\n")
        
        if not self.page:
            if not await self.connect():
                return False
        
        for step in range(self.max_steps):
            print(f"\n--- Step {step + 1}/{self.max_steps} ---")
            
            # 1. Get current DOM state (vision)
            print("[*] Capturing DOM tree...")
            dom = await self.get_dom_tree()
            
            if "error" in dom:
                print(f"[!] DOM error: {dom['error']}")
                await asyncio.sleep(2)
                continue
            
            print(f"    URL: {dom.get('url', 'unknown')}")
            print(f"    Title: {dom.get('title', 'unknown')}")
            
            # 2. Ask Llama for decision
            print("[*] Thinking...")
            decision = await self.ask_llama(goal, dom)
            
            action_type = decision.get("action", "")
            
            # 3. Check for completion
            if action_type == "done":
                success = decision.get("success", False)
                reason = decision.get("reason", "")
                print(f"\n[{'✓' if success else '✗'}] Goal {'ACHIEVED' if success else 'FAILED'}: {reason}")
                return success
            
            # 4. Execute action
            print("[*] Executing...")
            success = await self.execute_action(decision)
            
            if not success:
                self.history.append(f"FAILED: {decision}")
            
            # Small delay between steps
            await asyncio.sleep(1)
        
        print(f"\n[!] Max steps ({self.max_steps}) reached without completion")
        return False
    
    async def close(self):
        """Disconnect from browser (doesn't close Chrome)."""
        if self.browser:
            await self.browser.close()
            print("[*] Disconnected from browser")


# === CLI Interface ===
async def main():
    import sys
    
    goal = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "verify successful login on use.ai"
    
    agent = RAGBrowserAgent()
    
    try:
        success = await agent.run(goal)
        print(f"\n{'='*60}")
        print(f"Result: {'SUCCESS' if success else 'FAILED'}")
        print(f"{'='*60}")
        return 0 if success else 1
    finally:
        await agent.close()


if __name__ == "__main__":
    exit(asyncio.run(main()))
