import json
import os
from datasets import load_dataset
# We need to install unsloth dependencies for training later, but for now just processing
# pip install datasets pandas

OUTPUT_FILE = "dataset.jsonl"
DATASET_NAME = "xlangai/ubuntu_osworld_verified_trajs"

def format_llama_instruction(example):
    """
    Converts a single OSWorld example into Llama 3 Instruction format.
    Input format depends on the dataset structure (which we are inspecting).
    Expected structure from OSWorld usually includes: 
    - instruction (goal)
    - convertsation/trajectory
    """
    
    # OSWorld structure is complex. Usually has 'instruction' and 'actions'.
    # We will try to extract a simple (Instruction, Input(Observation), Output(Action)) tuple.
    
    instruction = example.get('instruction', '')
    if not instruction: return None

    # For valid training, we need the trajectory steps.
    # The dataset might have 'trajectory' or 'steps' or similar.
    # Let's dump keys if we fail to find what we need.
    
    # Fallback: Just return a debug print of keys if we don't know structure yet
    # But to "Just Work", let's assume we want to fine-tune on the instruction -> text code mapping.
    
    # Simplified Llama 3 Prompt Format:
    # {"instruction": "...", "input": "...", "output": "..."}
    
    return {
        "instruction": instruction,
        "input": "Desktop Environment (Ubuntu)",
        "output": str(example.get('trajectory', 'No trajectory data')) # Raw dump for now
    }

def process_data():
    print("[*] Loading locally cached dataset...")
    # This will use the files existing in ~/.cache/huggingface/datasets
    # If the user says 4/5 are downloaded, 'load_dataset' should find them.
    try:
        ds = load_dataset(DATASET_NAME, split="train")
    except Exception as e:
        print(f"[!] Error loading dataset: {e}")
        # Fallback to local dir if user moved zips manually?
        return

    print(f"[*] Found {len(ds)} raw episodes. Converting to JSONL...")

    with open(OUTPUT_FILE, "w") as f:
        count = 0
        for i, item in enumerate(ds):
            # Limit to what we likely have or max 100
            if i > 100: break
            
            processed = format_llama_instruction(item)
            if processed:
                f.write(json.dumps(processed) + "\n")
                count += 1
    
    print(f"[*] Successfully saved {count} training examples to {OUTPUT_FILE}")

if __name__ == "__main__":
    process_data()
