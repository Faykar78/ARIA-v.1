import json
import os
import glob
import requests
import base64
from brain import LocalBrain

# The Annotator uses the Agent's Brain to inspect the recording.
# It looks at the Screenshot + Action and guesses the "Instruction".

RECORDING_DIR = "training_data/ghost_logs"
OUTPUT_FILE = "training_data/annotated_dataset.jsonl"

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def annotate_recording():
    # 1. Init Brain (Using Ollama Llava)
    brain = LocalBrain(vision_model="qwen2.5vl:3b", action_model="qwen2.5vl:3b")
    
    # 2. Find Recording Sessions
    sessions = glob.glob(os.path.join(RECORDING_DIR, "*"))
    print(f"[*] Found {len(sessions)} recording sessions.")
    
    for session_path in sessions:
        log_path = os.path.join(session_path, "log.jsonl")
        if not os.path.exists(log_path): continue
        
        print(f"[*] Annotating Session: {os.path.basename(session_path)}")
        
        with open(log_path, 'r') as f:
            lines = f.readlines()
            
        # We group actions into "Chunks" (e.g., typing "hello" is 5 events, we want 1 instruction)
        # For simplicity in this demo, we annotate every 5th action or significant clicks.
        
        for i, line in enumerate(lines):
            event = json.loads(line)
            
            # Skip boring keypresses, focus on Clicks or 'Enter'
            if event['type'] == 'keypress' and event['details']['key'] not in ['Key.enter', 'Key.tab']:
                continue
                
            print(f"    -> Analyzing Action {i}: {event['type']}...")
            
            # 3. Ask Vision Model: "What is happening?"
            img_path = event['screenshot']
            if not os.path.exists(img_path): continue
            
            base64_img = encode_image(img_path)
            
            # Context for the model
            action_desc = f"User performed {event['type']} with details {event['details']}."
            
            prompt = (
                f"{action_desc}\n"
                "Look at the screen. What is the user trying to do?\n"
                "Return a short single-sentence GOAL (Instruction).\n"
                "Examples: 'Open Firefox', 'Search for Python', 'Close Window'."
                "Reply ONLY with the instruction."
            )
            
            # Use Brain's Vision (we hijack the analyze_screen method slightly or call API directly)
            # We'll use a direct API call here for custom prompt
            try:
                payload = {
                    "model": "llava",
                    "messages": [{"role": "user", "content": prompt, "images": [base64_img]}],
                    "stream": False
                }
                res = requests.post("http://localhost:11434/api/chat", json=payload)
                instruction = res.json()["message"]["content"].strip()
                
                print(f"       Guess: '{instruction}'")
                
                # 4. Save to Dataset
                training_example = {
                    "instruction": instruction,
                    "input": f"Screen Snapshot at {event['timestamp']}",
                    "output": json.dumps(event['details']) # The raw action is the target output
                }
                
                with open(OUTPUT_FILE, "a") as out:
                    out.write(json.dumps(training_example) + "\n")
                    
            except Exception as e:
                print(f"       Annotation Failed: {e}")

if __name__ == "__main__":
    annotate_recording()
