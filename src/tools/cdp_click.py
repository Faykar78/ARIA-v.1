#!/usr/bin/env python3
"""
CDP Click Tool - Click elements in Chrome using DevTools Protocol
"""

import asyncio
import json
import sys
from playwright.async_api import async_playwright

# WhatsApp-specific selectors for common actions (updated based on actual DOM)
WHATSAPP_SELECTORS = {
    # Menu / 3 dots - the main menu button
    "menu icon": '[aria-label="Menu"]',
    "menu": '[aria-label="Menu"]',
    "3 dots": '[aria-label="Menu"]',
    "triple dots": '[aria-label="Menu"]',
    "more": '[aria-label="Menu"]',
    
    # New chat button
    "new chat": '[aria-label="New chat"]',
    "new chat button": 'div[data-icon="new-chat-outline"]',
    
    # New group - in the menu dropdown
    "new group": 'div[aria-label="New group"], span:has-text("New group")',
    "create group": 'span:has-text("Create group")',
    
    # Search
    "search": '[aria-label="Search input textbox"]',
    "search box": 'div[data-icon="search-refreshed-thin"]',
    
    # Settings
    "settings": '[aria-label="Settings"]',
    
    # Chats tab
    "chats": '[aria-label="Chats"]',
    
    # Close button
    "close": '[aria-label="Close"]',
}

async def click_element(target: str):
    """Click an element in the active Chrome tab"""
    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            except Exception as e:
                print(json.dumps({"success": False, "error": f"No browser: {e}"}))
                return

            # Find the main page (not workers)
            context = browser.contexts[0]
            page = None
            for pg in context.pages:
                if "whatsapp" in (await pg.title()).lower() or "chrome" in (await pg.title()).lower():
                    page = pg
                    break
            
            if not page:
                page = context.pages[0] if context.pages else None
            
            if not page:
                print(json.dumps({"success": False, "error": "No pages found"}))
                return
            
            # Get selector for target
            target_lower = target.lower().strip()
            selector = WHATSAPP_SELECTORS.get(target_lower)
            
            if not selector:
                # Try general selectors
                selectors_to_try = [
                    f'span:has-text("{target}")',
                    f'div:has-text("{target}")',
                    f'button:has-text("{target}")',
                    f'[aria-label*="{target}"]',
                    f'[title*="{target}"]',
                ]
            else:
                selectors_to_try = [selector]
            
            clicked = False
            for sel in selectors_to_try:
                try:
                    locator = page.locator(sel).first
                    if await locator.count() > 0:
                        await locator.click(timeout=3000)
                        clicked = True
                        print(json.dumps({
                            "success": True, 
                            "action": "click",
                            "selector": sel,
                            "target": target
                        }))
                        break
                except Exception as e:
                    continue
            
            if not clicked:
                # Last resort: try to find by visible text
                try:
                    await page.get_by_text(target, exact=False).first.click(timeout=3000)
                    clicked = True
                    print(json.dumps({
                        "success": True,
                        "action": "click",
                        "method": "get_by_text",
                        "target": target
                    }))
                except:
                    print(json.dumps({
                        "success": False,
                        "error": f"Element not found: {target}"
                    }))
            
            await browser.close()
            
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))


async def type_text(text: str, target: str = ""):
    """Type text into an element or the focused element"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            
            # Find main page
            page = None
            for pg in context.pages:
                title = await pg.title()
                if "whatsapp" in title.lower():
                    page = pg
                    break
            if not page:
                page = context.pages[0] if context.pages else None
            
            if not page:
                print(json.dumps({"success": False, "error": "No page found"}))
                return
            
            typed = False
            
            if target:
                target_lower = target.lower().strip()
                selector = WHATSAPP_SELECTORS.get(target_lower)
                
                # Build a list of selectors to try
                selectors_to_try = []
                if selector:
                    selectors_to_try.append(selector)
                
                selectors_to_try.extend([
                    f'[aria-label="{target}"]',
                    f'[aria-label*="{target}"]',
                    f'div[contenteditable="true"][aria-label*="{target.split()[0]}"]',
                    'div[contenteditable="true"]',
                    f'input[placeholder*="{target}"]',
                    'input[type="text"]',
                ])
                
                for sel in selectors_to_try:
                    try:
                        loc = page.locator(sel).first
                        if await loc.count() > 0:
                            # Click first to focus
                            await loc.click(timeout=2000)
                            await page.wait_for_timeout(200)
                            
                            # Clear existing text and type new
                            await page.keyboard.press("Control+a")
                            await page.keyboard.type(text)
                            typed = True
                            print(json.dumps({
                                "success": True, 
                                "action": "type", 
                                "text": text,
                                "selector": sel
                            }))
                            break
                    except Exception as e:
                        continue
            
            if not typed:
                # Type to currently focused element
                await page.keyboard.type(text)
                print(json.dumps({"success": True, "action": "type", "text": text, "method": "keyboard"}))
            
            await browser.close()
            
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))


async def press_key(key: str):
    """Press a keyboard key"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0]
            
            await page.keyboard.press(key)
            print(json.dumps({"success": True, "action": "key", "key": key}))
            await browser.close()
            
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: cdp_click.py <action> <target>"}))
        sys.exit(1)
    
    action = sys.argv[1]
    target = sys.argv[2]
    
    if action == "click":
        asyncio.run(click_element(target))
    elif action == "type":
        asyncio.run(type_text(target))
    elif action == "key":
        asyncio.run(press_key(target))
    else:
        print(json.dumps({"error": f"Unknown action: {action}"}))
