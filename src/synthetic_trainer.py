import json
import time
import requests
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from detector import YoloDetector
from capture import ScreenCapture

OUTPUT_FILE = "training_data/synthetic_dataset.jsonl"
OLLAMA_URL = "http://localhost:11434/api/chat"

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def generate_synthetic_data(detector, capturer):
    print("\n=== Synthetic Trainer (AI Teaching AI) ===")
    print("[*] Open an app (Browser, Terminal, etc.) and wait 3 seconds...")
    time.sleep(3)
    
    # 1. Capture & Detect
    print("[*] Scanning Screen...")
    screenshot = capturer.capture()
    detections = detector.detect_and_ocr(screenshot)
    
    # 2. Format UI Elements for LLM
    visible_desc = []
    for i, item in enumerate(detections):
        text_info = f" (Text: '{item['text']}')" if item['text'] else ""
        desc = f"ID {i}: {item['label']}{text_info}"
        visible_desc.append(desc)
    
    elements_context = "\n".join(visible_desc)
    
    print(f"[*] Found {len(detections)} elements. Asking Llama to imagine tasks...")
    
    # 3. Prompt Llama to Hallucinate Data
    system_prompt = (
        "You are an expert AI Trainer.\n"
        "Generate 5 diverse 'User Goals' possible on this screen, and the corresponding correct JSON action.\n\n"
        "RESPONSE FORMAT (JSONL lines ONLY):\n"
        "{\"instruction\": \"Goal 1...\", \"input\": \"Visible: ID 0: File...\", \"output\": \"{\\\"action\\\": \\\"click\\\", \\\"selected_id\\\": 0}\"}\n"
    )
    
    user_prompt = (
        f"VISIBLE ELEMENTS:\n{elements_context}\n\n"
        "Generate 5 distinct training examples."
    )
    
    try:
        payload = {
            "model": "llama3.1",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {"temperature": 0.7} 
        }
        
        response = requests.post(OLLAMA_URL, json=payload)
        content = response.json()["message"]["content"]
        
        print("\n--- GENERATED DATA ---")
        print(content)
        print("----------------------")
        
        # 4. Save
        lines = content.strip().split('\n')
        saved_count = 0
        with open(OUTPUT_FILE, "a") as f:
            for line in lines:
                if line.startswith("{") and "instruction" in line:
                    f.write(line + "\n")
                    saved_count += 1
                    
        print(f"[+] Successfully harvested {saved_count} synthetic examples!")
        
    except Exception as e:
        print(f"[!] Error generating data: {e}")

if __name__ == "__main__":
    print("[*] Loading Models...")
    try:
        detector = YoloDetector("./ui_model.pt")
    except:
        detector = YoloDetector("yolov8n.pt")
        
    capturer = ScreenCapture()
    
    print("[*] Ready. Cycle through your apps.")
    while True:
        try:
            generate_synthetic_data(detector, capturer)
            input("\nPress Enter to scan next screen (or Ctrl+C to stop)...")
            clear()
        except KeyboardInterrupt:
            break
