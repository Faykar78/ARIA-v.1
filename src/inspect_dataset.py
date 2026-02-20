
from datasets import load_dataset
import json

print("[*] Loading Mind2Web (streaming)...")
# Stream to avoid downloading 10GB
ds = load_dataset("osunlp/Mind2Web", split="train", streaming=True)

print("[*] Inspecting first example...")
for ex in ds:
    print(json.dumps(ex, indent=2, default=str))
    break
