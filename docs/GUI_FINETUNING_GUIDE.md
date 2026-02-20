 # Qwen2.5-VL GUI Fine-tuning Quick Start Guide

## Overview

Train a local Qwen2.5-VL model to perform GUI automation tasks like clicking, typing, and navigating desktop applications.

## Prerequisites

```bash
# Core dependencies  
pip install pyautogui pillow pynput

# Fine-tuning dependencies
pip install transformers peft bitsandbytes accelerate datasets

# Optional: Flash Attention for faster training
pip install flash-attn --no-build-isolation
```

## Step 1: Collect Training Data

### Option A: Manual Recording (Recommended for First 100 Examples)

```bash
cd /home/harsha/Downloads/mightbe_done
python scripts/collect_gui_data.py --task "Click on the Chrome browser icon"
```

**Controls:**
- `Ctrl+R` - Start/pause recording
- Click anywhere - Records click action with coordinates
- Type + Enter - Records typing action
- `Ctrl+S` - Save current example, start new task
- `Ctrl+Q` - Save all and quit

### Option B: Synthetic Generation (Scale Up Quickly)

1. Take screenshots of various desktop states:
```bash
# Capture 50-100 screenshots of different UI states
import pyautogui
for i in range(50):
    screenshot = pyautogui.screenshot()
    screenshot.save(f"training_data/screenshots/desktop_{i:03d}.png")
    input("Press Enter to capture next...")
```

2. Generate training data:
```bash
python scripts/generate_synthetic_data.py --screenshots training_data/screenshots
```

## Step 2: Verify Training Data Format

Your JSONL file should look like:
```json
{"messages": [{"role": "user", "content": [{"type": "image", "image": "training_data/screenshots/desktop_001.png"}, {"type": "text", "text": "Open the terminal"}]}, {"role": "assistant", "content": [{"type": "text", "text": "I'll click on the terminal icon at (320, 1058). <action>click(320, 1058)</action>"}]}]}
```

## Step 3: Fine-tune the Model

```bash
# Basic training (requires ~24GB VRAM)
python scripts/train_gui_model.py \
    --data training_data/gui_training.jsonl \
    --output ./qwen2.5vl-gui-lora

# With 4-bit quantization (works on 8GB+ VRAM)
python scripts/train_gui_model.py \
    --data training_data/gui_training.jsonl \
    --output ./qwen2.5vl-gui-lora \
    --quantize
```

## Step 4: Use Your Fine-tuned Model

```python
from transformers import Qwen2VLForConditionalGeneration, Qwen2VLProcessor
from peft import PeftModel

# Load base model
base_model = Qwen2VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2.5-VL-7B-Instruct",
    device_map="auto",
    torch_dtype=torch.bfloat16
)

# Load LoRA adapter
model = PeftModel.from_pretrained(base_model, "./qwen2.5vl-gui-lora")
processor = Qwen2VLProcessor.from_pretrained("./qwen2.5vl-gui-lora")

# Use for inference
# ... (see brain.py for integration)
```

## Dataset Recommendations

| Task Type | Examples Needed |
|-----------|----------------|
| Basic clicks | 50-100 |
| Text typing | 50-100 |
| App opening | 30-50 |
| Menu navigation | 50-100 |
| Multi-step workflows | 100-200 |
| **Total** | **500-1000** |

## Integration with Clawdbot

After fine-tuning, update `src/brain.py` to use your local model:

```python
# In LocalBrain.__init__:
self.action_model = "./qwen2.5vl-gui-lora"

# Load with PEFT
from peft import PeftModel
self.model = PeftModel.from_pretrained(base_model, self.action_model)
```

## Tips

1. **Start small**: Collect 100 examples, train, test, iterate
2. **Include failures**: Add examples of what NOT to do
3. **Diverse screenshots**: Different apps, window states, themes
4. **Clear instructions**: Natural language like a user would say
5. **Accurate coordinates**: Use the actual pixel positions on screen
