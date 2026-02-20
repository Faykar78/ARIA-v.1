#!/usr/bin/env python3
"""
OSWorld to OmniParser Training Data Converter

This script:
1. Extracts OSWorld trajectory data from the cached dataset (traj.jsonl files)
2. Converts pyautogui action trajectories to our action format
3. Creates training data for fine-tuning Llama to understand screen coordinates

Target Format:
{
    "instruction": "User goal + step description",
    "input": "Screenshot observation context",
    "output": '{"action": "click", "x": 500, "y": 300, "reason": "..."}'
}
"""

import os
import sys
import json
import zipfile
import tempfile
import re
from pathlib import Path

# Config
CACHE_DIR = os.path.expanduser("~/.cache/huggingface/hub/datasets--xlangai--ubuntu_osworld_verified_trajs/snapshots/")
OUTPUT_FILE = "training_data/osworld_training.jsonl"

def find_snapshot_dir():
    """Find the latest snapshot directory."""
    if not os.path.exists(CACHE_DIR):
        print(f"[!] Cache directory not found: {CACHE_DIR}")
        return None
    
    snapshots = os.listdir(CACHE_DIR)
    if not snapshots:
        print("[!] No snapshots found")
        return None
    
    return os.path.join(CACHE_DIR, snapshots[0])

def parse_pyautogui_action(action_code):
    """
    Parse pyautogui action code to extract action type and coordinates.
    
    Examples:
    - pyautogui.click(288.0, 75.6, button='left') -> {"action": "click", "x": 288, "y": 75}
    - pyautogui.moveTo(637.44, 307.8) -> {"action": "move", "x": 637, "y": 307}
    - pyautogui.dragTo(700.8, 435.24, duration=1.0) -> {"action": "drag", "x": 700, "y": 435}
    - pyautogui.typewrite("text") -> {"action": "type", "text": "text"}
    - pyautogui.press("enter") -> {"action": "hotkey", "key": "enter"}
    """
    if not action_code or action_code == "DONE":
        return {"action": "done", "reason": "Task complete"}
    
    # Extract click
    click_match = re.search(r'pyautogui\.click\s*\(\s*([\d.]+)\s*,\s*([\d.]+)', action_code)
    if click_match:
        x, y = float(click_match.group(1)), float(click_match.group(2))
        return {"action": "click", "x": int(x), "y": int(y), "reason": "Click at coordinates"}
    
    # Extract double click
    dclick_match = re.search(r'pyautogui\.doubleClick\s*\(\s*([\d.]+)\s*,\s*([\d.]+)', action_code)
    if dclick_match:
        x, y = float(dclick_match.group(1)), float(dclick_match.group(2))
        return {"action": "double_click", "x": int(x), "y": int(y), "reason": "Double click"}
    
    # Extract moveTo
    move_match = re.search(r'pyautogui\.moveTo\s*\(\s*([\d.]+)\s*,\s*([\d.]+)', action_code)
    if move_match:
        x, y = float(move_match.group(1)), float(move_match.group(2))
        return {"action": "move", "x": int(x), "y": int(y), "reason": "Move cursor"}
    
    # Extract dragTo
    drag_match = re.search(r'pyautogui\.dragTo\s*\(\s*([\d.]+)\s*,\s*([\d.]+)', action_code)
    if drag_match:
        x, y = float(drag_match.group(1)), float(drag_match.group(2))
        return {"action": "drag", "x": int(x), "y": int(y), "reason": "Drag to position"}
    
    # Extract typewrite/write
    type_match = re.search(r'pyautogui\.(typewrite|write)\s*\([\'"](.+?)[\'"]\)', action_code)
    if type_match:
        text = type_match.group(2)
        return {"action": "type", "text": text, "reason": "Type text"}
    
    # Extract press/hotkey
    press_match = re.search(r'pyautogui\.(press|hotkey)\s*\([\'"](.+?)[\'"]\)', action_code)
    if press_match:
        key = press_match.group(2)
        return {"action": "hotkey", "key": key, "reason": "Press key"}
    
    # Extract scroll
    scroll_match = re.search(r'pyautogui\.scroll\s*\(\s*(-?\d+)', action_code)
    if scroll_match:
        amount = int(scroll_match.group(1))
        direction = "up" if amount > 0 else "down"
        return {"action": "scroll", "direction": direction, "amount": abs(amount), "reason": "Scroll"}
    
    # Check for specialized tool calls (autoglm format)
    if "WriterTools" in action_code or "Tools." in action_code:
        # Extract the function call
        call_match = re.search(r'(\w+Tools?\.\w+)\(', action_code)
        if call_match:
            return {"action": "app_function", "function": call_match.group(1), "raw": action_code[:100], "reason": "App-specific function"}
    
    return None

def extract_thought(action_code):
    """Extract the thought/reasoning from the action code."""
    # Look for <think>...</think> or Thought: pattern
    think_match = re.search(r'<think>(.*?)</think>', action_code, re.DOTALL)
    if think_match:
        return think_match.group(1).strip()[:500]
    
    thought_match = re.search(r"Thought:\s*\n(.+?)(?:\n'''|\n```)", action_code, re.DOTALL)
    if thought_match:
        return thought_match.group(1).strip()[:500]
    
    return ""

def get_task_from_path(path):
    """Extract task description from folder name."""
    parts = path.split('/')
    for part in parts:
        if part in ['libreoffice_writer', 'libreoffice_calc', 'firefox', 'chrome', 'thunderbird', 'vlc', 'gimp']:
            return part.replace('_', ' ').title()
    return "Desktop Task"

def process_traj_jsonl(traj_content, task_domain):
    """Process a traj.jsonl content and extract training examples."""
    examples = []
    
    lines = traj_content.strip().split('\n')
    
    for line in lines:
        if not line.strip():
            continue
        
        try:
            step = json.loads(line)
        except:
            continue
        
        step_num = step.get('step_num', 0)
        action_code = step.get('action', '')
        screenshot = step.get('screenshot_file', '')
        is_done = step.get('done', False)
        
        # Parse the action
        parsed_action = parse_pyautogui_action(action_code)
        if not parsed_action:
            continue
        
        # Extract reasoning
        thought = extract_thought(action_code)
        if thought:
            parsed_action['reason'] = thought[:200]
        
        # Create instruction based on thought or action type
        if thought:
            # Take first sentence as instruction
            instruction = thought.split('.')[0].strip()
            if len(instruction) < 10:
                instruction = f"{task_domain} - Step {step_num}"
        else:
            instruction = f"{task_domain} - {parsed_action['action']} action"
        
        # Create input context
        input_context = f"Active Window: {task_domain}. Screenshot: {screenshot}. Step {step_num} of task."
        
        example = {
            "instruction": instruction,
            "input": input_context,
            "output": json.dumps(parsed_action)
        }
        
        examples.append(example)
    
    return examples

def extract_and_process_zip(zip_path, output_examples):
    """Extract a zip file and process all traj.jsonl files."""
    zip_name = os.path.basename(zip_path)
    print(f"[*] Processing: {zip_name}")
    
    count = 0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # List all traj.jsonl files
                traj_files = [f for f in zf.namelist() if f.endswith('traj.jsonl')]
                print(f"    Found {len(traj_files)} trajectory files")
                
                for traj_path in traj_files[:100]:  # Limit for first run
                    try:
                        # Get task domain from path
                        task_domain = get_task_from_path(traj_path)
                        
                        # Read content
                        with zf.open(traj_path) as f:
                            content = f.read().decode('utf-8')
                        
                        # Process
                        examples = process_traj_jsonl(content, task_domain)
                        output_examples.extend(examples)
                        count += len(examples)
                        
                    except Exception as e:
                        print(f"    [!] Error processing {traj_path}: {e}")
                
        except Exception as e:
            print(f"    [!] Error extracting zip: {e}")
    
    print(f"    Extracted {count} training examples")
    return count

def add_synthetic_omniparser_examples():
    """Add synthetic examples in OmniParser element format for the model to learn."""
    
    return [
        # Click actions on detected elements
        {
            "instruction": "Click the Submit button",
            "input": 'Active Window: Form. Visible Elements: [{"id": 0, "type": "text_input", "text": "Name", "center": "(300,200)"}, {"id": 1, "type": "text_input", "text": "Email", "center": "(300,250)"}, {"id": 2, "type": "button", "text": "Submit", "center": "(350,320)"}, {"id": 3, "type": "button", "text": "Cancel", "center": "(450,320)"}]',
            "output": '{"action": "click", "target_id": 2, "x": 350, "y": 320, "reason": "Submit button matches user goal"}'
        },
        {
            "instruction": "Open Chrome browser", 
            "input": 'Active Window: Ubuntu Desktop. Visible Elements: [{"id": 0, "type": "icon", "text": "Files", "center": "(50,100)"}, {"id": 1, "type": "icon", "text": "Chrome", "center": "(50,150)"}, {"id": 2, "type": "icon", "text": "Terminal", "center": "(50,200)"}]',
            "output": '{"action": "click", "target_id": 1, "x": 50, "y": 150, "reason": "Chrome icon to open browser"}'
        },
        {
            "instruction": "Type hello in the search box",
            "input": 'Active Window: Google Chrome. Visible Elements: [{"id": 0, "type": "text_input", "text": "Search", "center": "(500,60)"}, {"id": 1, "type": "button", "text": "Google Search", "center": "(500,120)"}]',
            "output": '{"action": "click", "target_id": 0, "x": 500, "y": 60, "reason": "Focus search box first"}'
        },
        {
            "instruction": "Scroll down to see more",
            "input": 'Active Window: Web Page. Visible Elements: [{"id": 0, "type": "text", "text": "Article content...", "center": "(500,300)"}, {"id": 1, "type": "link", "text": "Read more", "center": "(500,700)"}]',
            "output": '{"action": "scroll", "direction": "down", "amount": 300, "reason": "Scroll to reveal more content"}'
        },
        {
            "instruction": "Close the popup",
            "input": 'Active Window: Popup Dialog. Visible Elements: [{"id": 0, "type": "button", "text": "X", "center": "(700,100)"}, {"id": 1, "type": "text", "text": "Subscribe", "center": "(500,200)"}, {"id": 2, "type": "button", "text": "Subscribe", "center": "(500,300)"}]',
            "output": '{"action": "click", "target_id": 0, "x": 700, "y": 100, "reason": "X button closes popup"}'
        },
        {
            "instruction": "Click Format menu",
            "input": 'Active Window: LibreOffice Writer. Visible Elements: [{"id": 0, "type": "menu", "text": "File", "center": "(40,30)"}, {"id": 1, "type": "menu", "text": "Edit", "center": "(80,30)"}, {"id": 2, "type": "menu", "text": "View", "center": "(120,30)"}, {"id": 3, "type": "menu", "text": "Format", "center": "(170,30)"}]',
            "output": '{"action": "click", "target_id": 3, "x": 170, "y": 30, "reason": "Open Format menu"}'
        },
        {
            "instruction": "Select all text",
            "input": 'Active Window: Text Editor. Visible Elements: [{"id": 0, "type": "text_area", "text": "Document content here...", "center": "(400,300)"}]',
            "output": '{"action": "hotkey", "key": "ctrl+a", "reason": "Select all text with keyboard shortcut"}'
        },
        {
            "instruction": "Save the document",
            "input": 'Active Window: Document Editor. Visible Elements: [{"id": 0, "type": "menu", "text": "File", "center": "(40,30)"}, {"id": 1, "type": "toolbar_button", "text": "Save", "center": "(60,70)"}]',
            "output": '{"action": "hotkey", "key": "ctrl+s", "reason": "Save document with keyboard shortcut"}'
        },
        {
            "instruction": "Open WhatsApp",
            "input": 'Active Window: Ubuntu Desktop. Visible Elements: [{"id": 0, "type": "taskbar", "text": "Activities", "center": "(50,10)"}, {"id": 1, "type": "dock_icon", "text": "Chrome", "center": "(50,400)"}]',
            "output": '{"action": "browse", "url": "web.whatsapp.com", "reason": "Open WhatsApp Web in browser"}'
        },
        {
            "instruction": "Send message hi to John",
            "input": 'Active Window: WhatsApp Web. Visible Elements: [{"id": 0, "type": "chat", "text": "John", "center": "(150,200)"}, {"id": 1, "type": "text_input", "text": "Type a message", "center": "(500,700)"}]',
            "output": '{"action": "send_message", "message": "hi", "recipient": "John", "reason": "Send message via WhatsApp"}'
        },
    ]

def main():
    print("=" * 60)
    print("OSWorld to OmniParser Training Data Converter")
    print("=" * 60)
    
    # Find dataset
    snapshot_dir = find_snapshot_dir()
    if not snapshot_dir:
        print("[!] Dataset not found. Please ensure OSWorld dataset is cached.")
        return
    
    print(f"[*] Found snapshot: {snapshot_dir}")
    
    # List available files
    files = os.listdir(snapshot_dir)
    zip_files = [f for f in files if f.endswith('.zip')]
    
    print(f"[*] Found {len(zip_files)} trajectory archives:")
    for zf in zip_files:
        print(f"    - {zf}")
    
    # Process each zip
    all_examples = []
    
    for zf in zip_files:
        zip_path = os.path.join(snapshot_dir, zf)
        extract_and_process_zip(zip_path, all_examples)
    
    # Add synthetic OmniParser examples
    synthetic = add_synthetic_omniparser_examples()
    all_examples.extend(synthetic)
    
    # Save
    os.makedirs("training_data", exist_ok=True)
    
    with open(OUTPUT_FILE, 'w') as f:
        for ex in all_examples:
            f.write(json.dumps(ex) + "\n")
    
    osworld_count = len(all_examples) - len(synthetic)
    
    print(f"\n[+] Saved {len(all_examples)} training examples to {OUTPUT_FILE}")
    print(f"    - From OSWorld: {osworld_count}")
    print(f"    - Synthetic: {len(synthetic)}")
    
    # Show sample
    if all_examples:
        print("\n[*] Sample training examples:")
        for i, sample in enumerate(all_examples[:3]):
            print(f"\n  Example {i+1}:")
            print(f"    Instruction: {sample['instruction'][:60]}...")
            print(f"    Input: {sample['input'][:60]}...")
            print(f"    Output: {sample['output'][:80]}...")

if __name__ == "__main__":
    main()
