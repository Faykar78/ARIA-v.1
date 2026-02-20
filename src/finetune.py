
import os
import sys
import json
import torch
from datasets import Dataset

# MEMORY FIX:
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

def check_gpu():
    if not torch.cuda.is_available():
        print("[-] GPU not detected. Training will be extremely slow (CPU). Aborting.")
        sys.exit(1)
    vram = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"[+] GPU Detected: {torch.cuda.get_device_name(0)} ({vram:.1f} GB VRAM)")
    return vram

def train_lora():
    print("[*] Starting Fine-Tuning Process...")
    check_gpu()
    
    # 1. Load Data
    data_path = "training_data/final_finetune_data.jsonl"
    print(f"[*] Loading dataset from {data_path}...")
    
    entries = []
    with open(data_path, 'r') as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    
    print(f"[+] Loaded {len(entries)} training examples.")
    if len(entries) < 10:
        print("[!] Warning: Dataset is tiny. Overfitting likely.")
        
    # Convert to Alpaca/Instruction format
    # Instruction: <instruction>
    # Input: <input>
    # Output: <output>
    
    formatted_data = []
    for e in entries:
        # TRUNCATION FIX: Limit input length to prevent OOM
        inp_str = e.get('input', '')
        if len(inp_str) > 1000:
            inp_str = inp_str[:1000] + "...(truncated)"
            
        prompt = f"""Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{e['instruction']}

### Input:
{inp_str}

### Response:
{e['output']}
"""
        formatted_data.append({"text": prompt})
    
    dataset = Dataset.from_list(formatted_data)
    
    # 2. Setup Unsloth (Preferred) or PEFT
    try:
        from unsloth import FastLanguageModel
        print("[+] Unsloth library found. Optimizing for 4060...")
        
        model_name = "unsloth/Meta-Llama-3.1-8B-bnb-4bit" # 4bit Quantized base
        max_seq_length = 512 # Drastic reduction to 512 to ensure fit
        dtype = None # Auto detection
        load_in_4bit = True 

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name = model_name,
            max_seq_length = max_seq_length,
            dtype = dtype,
            load_in_4bit = load_in_4bit,
        )

        model = FastLanguageModel.get_peft_model(
            model,
            r = 8, # Reduced Rank from 16 to 8
            target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                              "gate_proj", "up_proj", "down_proj",],
            lora_alpha = 16,
            lora_dropout = 0, # Supports any, but = 0 is optimized
            bias = "none",    # Supports any, but = "none" is optimized
            use_gradient_checkpointing = "unsloth", 
            random_state = 3407,
            use_rslora = False,
            loftq_config = None,
        )
        
        from trl import SFTTrainer
        from transformers import TrainingArguments
        
        trainer = SFTTrainer(
            model = model,
            tokenizer = tokenizer,
            train_dataset = dataset,
            dataset_text_field = "text",
            max_seq_length = max_seq_length,
            dataset_num_proc = 2,
            packing = False, # Can make training 5x faster for short sequences
            args = TrainingArguments(
                per_device_train_batch_size = 1, 
                gradient_accumulation_steps = 8,
                warmup_steps = 5,
                max_steps = 60, # Small dataset = few steps
                learning_rate = 2e-4,
                fp16 = not torch.cuda.is_bf16_supported(),
                bf16 = torch.cuda.is_bf16_supported(),
                logging_steps = 1,
                optim = "adamw_8bit",
                weight_decay = 0.01,
                lr_scheduler_type = "linear",
                seed = 3407,
                output_dir = "outputs",
            ),
        )
        
        print("[*] Training...")
        trainer.train()
        
        print("[+] Training Complete.")
        
        # 3. Save GGUF (for Ollama)
        print("[*] Exporting to GGUF (q4_k_m) for Ollama...")
        model.save_pretrained_gguf("antigravity_model", tokenizer, quantization_method = "q4_k_m")
        print("[+] Model saved to 'antigravity_model-unsloth.Q4_K_M.gguf'")
        
    except ImportError as e:
        print(f"[-] Unsloth not found ({e}). Please install dependencies.")
        print("    pip install \"unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git\"")
        print("    pip install --no-deps xformers trl peft accelerate bitsandbytes")

if __name__ == "__main__":
    train_lora()
