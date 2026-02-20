from unsloth import FastLanguageModel
import os

# Enable consistent memory behavior just in case
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

model_name = "outputs/checkpoint-60" # Local checkpoint
max_seq_length = 512
dtype = None
load_in_4bit = True

print("[*] Loading trained model from checkpoint...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = model_name,
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)

print("[*] Converting to GGUF (q4_k_m)...")
# This will trigger the base model download if not cached
model.save_pretrained_gguf("antigravity_model", tokenizer, quantization_method = "q4_k_m")
print("[+] GGUF Export Successful!")
