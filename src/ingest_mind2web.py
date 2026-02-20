
import json
import os
from datasets import load_dataset

OUTPUT_FILE = "training_data/manual_dataset.jsonl"
LIMIT = 50 

def extract_description(candidate):
    """Extracts a text description from HTML attributes."""
    try:
        attrs = json.loads(candidate.get("attributes", "{}"))
    except:
        attrs = {}
    
    # Priority: aria-label > text > title > name > class
    if "aria-label" in attrs: return attrs["aria-label"]
    if "text" in candidate and candidate["text"]: return candidate["text"] # Some datasets have this
    if "title" in attrs: return attrs["title"]
    if "name" in attrs: return attrs["name"]
    
    tag = candidate.get("tag", "element")
    return f"{tag} element"

print("[*] Loading Mind2Web (streaming)...")
try:
    ds = load_dataset("osunlp/Mind2Web", split="train", streaming=True)
except Exception as e:
    print(f"[!] Failed to load dataset: {e}")
    exit(1)


print(f"[*] Extracting WhatsApp/Chat examples (Limit: {LIMIT})...")

count = 0
with open(OUTPUT_FILE, "a") as f:
    for ex in ds:
        if count >= LIMIT: break
        
        try:
            task = ex["confirmed_task"]
            website = ex["website"]
            
            # --- FILTER: WHATSAPP FOCUS ---
            # specifically look for whatsapp or general messaging interactions if whatsapp is rare
            keywords = ["whatsapp", "chat", "message", "text", "send", "reply", "contact"]
            if not any(k in task.lower() for k in keywords) and not "whatsapp" in website.lower():
                continue # Skip non-relevant tasks
            # ------------------------------
            
            # Action Mapping
            op_data = ex.get("operation", {})
            op_type = op_data.get("op", "").upper()
            
            action = {}
            
            # Get target description from positive candidates
            candidates = ex.get("pos_candidates", [])
            target_desc = "unknown element"
            if candidates:
                target_desc = extract_description(candidates[0])
            
            if op_type == "CLICK":
                action = {
                    "action": "click",
                    "target_description": target_desc,
                    "reason": f"Step from Mind2Web ({website})"
                }
            elif op_type in ["TYPE", "SELECT"]:
                value = op_data.get("value", "")
                action = {
                    "action": "type",
                    "text": value,
                    "reason": f"Step from Mind2Web ({website})"
                }
            else:
                continue # Skip unknown ops
                
            # Create Memory Entry
            entry = {
                "instruction": task,
                "input": f"Context: {website}. Active Element: {target_desc}",
                "output": json.dumps(action)
            }
            
            f.write(json.dumps(entry) + "\n")
            count += 1
            print(f"    [+] Ingested: {task[:50]}...")
            
        except Exception as e:
            print(f"    [!] Error parsing example: {e}")
            continue

print(f"[*] Successfully ingested {count} examples into Agent Memory.")
