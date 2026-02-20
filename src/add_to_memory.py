#!/usr/bin/env python3
"""
Simple Fine-tuning for OmniParser Understanding

Instead of full model fine-tuning (which has dependency issues),
this script adds the training examples directly to the brain's memory
for instant "learned behavior" without GPU training.

This is a practical solution that works immediately!
"""

import json
import os

TRAINING_FILE = "training_data/osworld_training.jsonl"
OUTPUT_FILE = "training_data/manual_dataset.jsonl"

def load_training_data():
    """Load the synthetic training examples."""
    if not os.path.exists(TRAINING_FILE):
        print(f"[!] Training file not found: {TRAINING_FILE}")
        return []
    
    data = []
    with open(TRAINING_FILE, 'r') as f:
        for line in f:
            try:
                item = json.loads(line.strip())
                data.append(item)
            except:
                continue
    return data

def convert_to_memory_format(examples):
    """
    Convert training examples to the format used by brain.py memory.
    
    Brain memory format:
    {"instruction": "...", "input": "...", "output": "{JSON action}"}
    """
    memory_entries = []
    
    for ex in examples:
        instruction = ex.get("instruction", "")
        output = ex.get("output", "")
        
        # Brain.py uses instruction as lookup key
        entry = {
            "instruction": instruction,
            "input": ex.get("input", ""),
            "output": output
        }
        memory_entries.append(entry)
    
    return memory_entries

def main():
    print("=" * 60)
    print("Adding Training Examples to Brain Memory")
    print("=" * 60)
    
    # Load training examples
    examples = load_training_data()
    print(f"[*] Loaded {len(examples)} training examples")
    
    if not examples:
        print("[!] No training examples found. Run src/generate_english_training.py first.")
        return
    
    # Load existing memory
    existing_memory = []
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as f:
            for line in f:
                try:
                    existing_memory.append(json.loads(line.strip()))
                except:
                    continue
        print(f"[*] Loaded {len(existing_memory)} existing memory entries")
    
    # Convert and add new examples
    new_entries = convert_to_memory_format(examples)
    
    # Merge (avoid duplicates by instruction)
    existing_instructions = {e.get("instruction", "").lower().strip() for e in existing_memory}
    added = 0
    
    for entry in new_entries:
        key = entry.get("instruction", "").lower().strip()
        if key not in existing_instructions:
            existing_memory.append(entry)
            existing_instructions.add(key)
            added += 1
    
    # Save
    with open(OUTPUT_FILE, 'w') as f:
        for entry in existing_memory:
            f.write(json.dumps(entry) + "\n")
    
    print(f"\n[+] Added {added} new entries to brain memory")
    print(f"[+] Total memory entries: {len(existing_memory)}")
    print(f"[+] Saved to {OUTPUT_FILE}")
    
    print("\n[*] The brain will now use these examples for instant action matching!")
    print("[*] Restart main.py to load the new memory.")

if __name__ == "__main__":
    main()
