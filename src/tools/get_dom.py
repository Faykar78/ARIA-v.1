
import asyncio
from playwright.async_api import async_playwright
import json
import sys

async def get_dom_tree():
    try:
        async with async_playwright() as p:
            # Connect to the persistent browser
            try:
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            except:
                print("No browser found on port 9222.")
                return

            context = browser.contexts[0]
            page = context.pages[0] # Assume focused page

            # Get Accessibility Tree (Semantic DOM)
            # This is better for LLMs than raw HTML
            snapshot = await page.accessibility.snapshot()
            
            # Helper to flatten or summarize
            def simplify(node, depth=0):
                if depth > 10: return None # Prune deep trees
                info = {
                    "role": node.get("role"),
                    "name": node.get("name"),
                }
                # Optional: Add value/text if present
                if "value" in node: info["value"] = node["value"]
                if "description" in node: info["desc"] = node["description"]
                
                children = node.get("children", [])
                if children:
                    info["children"] = [simplify(c, depth+1) for c in children if simplify(c, depth+1)]
                
                # Filter noise (empty containers)
                if not info.get("name") and not info.get("value") and not info.get("children"):
                    return None
                    
                return info

            simplified_tree = simplify(snapshot)
            print(json.dumps(simplified_tree, indent=2))
            
            await browser.close()
            
    except Exception as e:
        print(f"Error getting DOM: {e}")

if __name__ == "__main__":
    asyncio.run(get_dom_tree())
