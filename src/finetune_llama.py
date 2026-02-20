#!/usr/bin/env python3
"""
Fine-tune Llama for OmniParser UI Understanding using PEFT/LoRA

This script creates a LoRA adapter for Llama that understands:
1. OmniParser element format with IDs, types, text, and coordinates
2. Screen coordinates from OSWorld trajectories
3. How to map user goals to appropriate actions

Uses standard PEFT library for compatibility.

Requirements:
    pip install transformers datasets peft accelerate bitsandbytes trl
"""

import os
import sys
import json
import torch
from pathlib import Path

# Training Config
MODEL_NAME = "meta-llama/Llama-3.1-8B"  # Will be loaded in 4-bit
OUTPUT_DIR = "models/antigravity-lora"
TRAINING_FILE = "training_data/osworld_training.jsonl"

# LoRA Config
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

# Training Hyperparameters
BATCH_SIZE = 2
GRADIENT_ACCUMULATION = 4
LEARNING_RATE = 2e-4
NUM_EPOCHS = 2
MAX_SEQ_LENGTH = 1024
WARMUP_RATIO = 0.03

# System prompt for the model
SYSTEM_PROMPT = """You are Antigravity, an AI GUI automation agent. You receive:
1. A user goal (what they want to accomplish)
2. Context about the active window and visible UI elements

You must output a JSON action to accomplish the goal. Available actions:
- {"action": "click", "x": N, "y": M, "reason": "why"} - Click at screen coordinates
- {"action": "click", "target_id": N, "reason": "why"} - Click element by ID
- {"action": "type", "text": "...", "reason": "why"} - Type text
- {"action": "hotkey", "key": "...", "reason": "why"} - Press key combo
- {"action": "scroll", "direction": "up/down", "reason": "why"} - Scroll
- {"action": "done", "reason": "task complete"} - Task finished

Always output ONLY valid JSON. Be precise with coordinates."""

def load_training_data():
    """Load and format training data."""
    if not os.path.exists(TRAINING_FILE):
        print(f"[!] Training file not found: {TRAINING_FILE}")
        print("[*] Run src/train_osworld.py first to generate training data.")
        return None
    
    data = []
    with open(TRAINING_FILE, 'r') as f:
        for line in f:
            try:
                item = json.loads(line.strip())
                data.append(item)
            except:
                continue
    
    print(f"[*] Loaded {len(data)} training examples")
    return data

def format_conversation(item):
    """Format a single item into a conversation for training."""
    instruction = item.get("instruction", "")
    input_text = item.get("input", "")
    output = item.get("output", "")
    
    # Combine instruction and input
    user_content = f"Goal: {instruction}"
    if input_text:
        user_content += f"\n\n{input_text}"
    
    # Return as a conversation
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": output}
        ]
    }

def train():
    """Train the model using PEFT/LoRA."""
    
    try:
        from transformers import (
            AutoModelForCausalLM, 
            AutoTokenizer, 
            BitsAndBytesConfig,
            TrainingArguments
        )
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from trl import SFTTrainer, DataCollatorForCompletionOnlyLM
        from datasets import Dataset
    except ImportError as e:
        print(f"[!] Missing dependencies: {e}")
        print("[*] Install with: pip install transformers datasets peft accelerate bitsandbytes trl")
        return False
    
    # Load training data
    data = load_training_data()
    if not data:
        return False
    
    # Format for training
    formatted_data = [format_conversation(item) for item in data]
    dataset = Dataset.from_list(formatted_data)
    
    print(f"\n[*] Loading model: {MODEL_NAME}")
    print("[*] Using 4-bit quantization for memory efficiency...")
    
    # 4-bit quantization config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    
    # Load model with 4-bit quantization
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    
    # Prepare for k-bit training
    model = prepare_model_for_kbit_training(model)
    
    # LoRA configuration
    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=TARGET_MODULES,
        bias="none",
        task_type="CAUSAL_LM",
    )
    
    # Apply LoRA
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION,
        warmup_ratio=WARMUP_RATIO,
        num_train_epochs=NUM_EPOCHS,
        learning_rate=LEARNING_RATE,
        fp16=True,
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        optim="paged_adamw_8bit",
        report_to="none",
    )
    
    # Format function for SFTTrainer
    def formatting_func(example):
        messages = example["messages"]
        text = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                text += f"<|start_header_id|>system<|end_header_id|>\n{content}<|eot_id|>"
            elif role == "user":
                text += f"<|start_header_id|>user<|end_header_id|>\n{content}<|eot_id|>"
            elif role == "assistant":
                text += f"<|start_header_id|>assistant<|end_header_id|>\n{content}<|eot_id|>"
        return text
    
    # Create trainer
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=training_args,
        formatting_func=formatting_func,
        max_seq_length=MAX_SEQ_LENGTH,
        packing=True,
    )
    
    print("\n" + "=" * 60)
    print("Starting Training...")
    print("=" * 60)
    print(f"  Model: {MODEL_NAME}")
    print(f"  Training examples: {len(dataset)}")
    print(f"  Batch size: {BATCH_SIZE} x {GRADIENT_ACCUMULATION} = {BATCH_SIZE * GRADIENT_ACCUMULATION}")
    print(f"  Epochs: {NUM_EPOCHS}")
    print(f"  Learning rate: {LEARNING_RATE}")
    print("=" * 60 + "\n")
    
    # Train
    trainer.train()
    
    # Save
    print(f"\n[*] Saving LoRA adapter to {OUTPUT_DIR}...")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    
    print("\n[+] Training complete!")
    return True

def create_ollama_modelfile():
    """Create Ollama Modelfile for the fine-tuned model."""
    modelfile = f"""FROM llama3.1

# System prompt for GUI automation
SYSTEM \"\"\"{SYSTEM_PROMPT}\"\"\"

PARAMETER temperature 0.1
PARAMETER num_ctx 2048
PARAMETER stop "<|eot_id|>"
"""
    
    with open("Antigravity-trained.Modelfile", "w") as f:
        f.write(modelfile)
    
    print("\n[*] Created Antigravity-trained.Modelfile")
    print("[*] To create Ollama model after GGUF conversion:")
    print("    ollama create antigravity-trained -f Antigravity-trained.Modelfile")

def main():
    print("=" * 60)
    print("Antigravity - OmniParser Fine-Tuning (PEFT/LoRA)")
    print("=" * 60)
    
    # Check GPU
    if torch.cuda.is_available():
        print(f"[+] GPU: {torch.cuda.get_device_name(0)}")
        mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"    Memory: {mem:.1f} GB")
        
        if mem < 8:
            print("[!] Warning: Low GPU memory. Training may be slow or fail.")
    else:
        print("[!] No GPU detected. Training will be very slow.")
    
    # Check if training data exists
    if not os.path.exists(TRAINING_FILE):
        print(f"\n[!] Training data not found: {TRAINING_FILE}")
        print("[*] Generating training data first...")
        os.system("python3 src/train_osworld.py")
    
    # Train
    success = train()
    
    if success:
        create_ollama_modelfile()
    
    return success

if __name__ == "__main__":
    main()
