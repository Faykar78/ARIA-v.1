import json
import os
import time
import sys

# Add src to path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from detector import YoloDetector
from capture import ScreenCapture

DATASET_FILE = "training_data/manual_dataset.jsonl"
MODELS_DIR = "./" # Assuming main dir

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def add_example(detector, capturer):
    print("\n=== Antigravity Trainer (Live Mode) ===")
    
    # 1. The Goal
    instruction = input("1. User Goal (e.g., 'Open Terminal'): ").strip()
    if not instruction: return

    # 2. Capture Real Context
    print("\n[!] Prepare the screen! capture in 3 seconds...")
    time.sleep(3)
    
    print("[*] Capturing & Detecting...")
    screenshot = capturer.capture()
    detections = detector.detect_and_ocr(screenshot)
    
    print("\n--- I SEE THESE ELEMENTS ---")
    visible_desc = []
    
    for i, item in enumerate(detections):
        text_info = f" (Text: '{item['text']}')" if item['text'] else ""
        desc = f"ID {i}: {item['label']}{text_info}"
        visible_desc.append(desc)
        print(desc)
    
    print("----------------------------")
    
    active_window = "Unknown (Assume Active)" # Can improve later with xdotool
    formatted_input = f"Active Window: {active_window}. Visible Elements: {', '.join(visible_desc)}"

    # 3. The Correct Action
    print("\n2. What is the Correct Action?")
    print("   (Use the IDs above if clicking/typing)")
    print("   Types: click, type, hotkey, launch, wait")
    
    action_type = input("   Action Type: ").strip().lower()
    action_dict = {"action": action_type}
    
    if action_type == "click":
        try:
            sel_id = int(input("   Which ID?: "))
            action_dict["selected_id"] = sel_id
            # Verify ID exists
            if sel_id < 0 or sel_id >= len(detections):
                 print("[!] Warning: ID out of range, but saving anyway.")
        except ValueError:
            print("[!] Invalid ID.")
            return

    elif action_type == "type":
        action_dict["text"] = input("   Text to type: ")
        
    elif action_type == "hotkey":
        keys = input("   Keys (comma sep): ").split(',')
        action_dict["keys"] = [k.strip() for k in keys]
        
    elif action_type == "launch":
        action_dict["app"] = input("   App command: ")

    reason = input("   Reasoning: ")
    action_dict["reason"] = reason

    # 4. Save
    entry = {
        "instruction": instruction,
        "input": formatted_input,
        "output": json.dumps(action_dict)
    }

    with open(DATASET_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"\n[+] Saved Lesson! (Total: {len(open(DATASET_FILE).readlines())})")

if __name__ == "__main__":
    print("[*] Loading Detector (One-time setup)...")
    try:
        # Looking for model in current dir or fallback
        model_path = "./ui_model.pt"
        detector = YoloDetector(model_path)
    except Exception as e:
        print(f"[!] Custom model not found ({e}). Using 'yolov8n.pt' as fallback for demo.")
        detector = YoloDetector("yolov8n.pt")
        
    print("[*] Initializing Screen Capture...")
    capturer = ScreenCapture()

    while True:
        try:
            add_example(detector, capturer)
            cont = input("\nAdd another? (y/n): ")
            if cont.lower() != 'y': break
        except KeyboardInterrupt:
            break

