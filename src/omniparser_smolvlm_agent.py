#!/usr/bin/env python3
"""
OmniParser + SmolVLM GUI Automation Pipeline

Two-stage pipeline optimized for RTX 4060 8GB VRAM:
1. OmniParser (CPU): Detects and labels UI elements with bounding boxes
2. SmolVLM (GPU): Selects action based on natural language instruction

Usage:
    python omniparser_smolvlm_agent.py --screenshot desktop.png --instruction "Open Chrome"
    
Models:
    - OmniParser V2: microsoft/OmniParser-v2.0
    - SmolVLM: HuggingFaceTB/SmolVLM-256M-Instruct
"""

import os
import sys
import json
import re
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
from PIL import Image, ImageDraw, ImageFont

# Model paths (will be downloaded on first run)
OMNIPARSER_DIR = Path("models/omniparser_v2")
SMOLVLM_DIR = Path("models/smolvlm_256m")


class OmniParserDetector:
    """
    Stage 1: OmniParser for UI element detection.
    Runs on CPU to preserve GPU VRAM for SmolVLM.
    """
    
    def __init__(self, model_dir: Path = OMNIPARSER_DIR):
        self.model_dir = model_dir
        self.icon_detector = None
        self.caption_model = None
        self.caption_processor = None
        self.loaded = False
    
    def download_models(self):
        """Download OmniParser V2 models if not present."""
        if not self.model_dir.exists():
            print("[OmniParser] Downloading models from HuggingFace...")
            self.model_dir.mkdir(parents=True, exist_ok=True)
            
            # Download using huggingface_hub
            try:
                from huggingface_hub import snapshot_download
                snapshot_download(
                    repo_id="microsoft/OmniParser-v2.0",
                    local_dir=str(self.model_dir),
                    local_dir_use_symlinks=False
                )
                print("[OmniParser] Models downloaded successfully")
            except Exception as e:
                print(f"[OmniParser] Download failed: {e}")
                print("Manual download: huggingface-cli download microsoft/OmniParser-v2.0 --local-dir models/omniparser_v2")
                raise
    
    def load(self):
        """Load OmniParser models to CPU."""
        if self.loaded:
            return
        
        self.download_models()
        
        print("[OmniParser] Loading icon detector (YOLO)...")
        try:
            from ultralytics import YOLO
            icon_model_path = self.model_dir / "icon_detect" / "model.pt"
            if not icon_model_path.exists():
                icon_model_path = self.model_dir / "icon_detect" / "best.pt"
            
            self.icon_detector = YOLO(str(icon_model_path))
            self.icon_detector.to('cpu')
        except Exception as e:
            print(f"[OmniParser] YOLO load error: {e}")
            print("Install ultralytics: pip install ultralytics")
            raise
        
        print("[OmniParser] Loading caption model (Florence-2)...")
        try:
            from transformers import AutoModelForCausalLM, AutoProcessor
            
            caption_model_path = self.model_dir / "icon_caption_florence"
            if not caption_model_path.exists():
                caption_model_path = self.model_dir / "icon_caption"
            
            self.caption_processor = AutoProcessor.from_pretrained(
                str(caption_model_path),
                trust_remote_code=True
            )
            
            self.caption_model = AutoModelForCausalLM.from_pretrained(
                str(caption_model_path),
                trust_remote_code=True,
                torch_dtype=torch.float32,  # CPU doesn't benefit from fp16
                device_map='cpu'
            )
        except Exception as e:
            print(f"[OmniParser] Florence load error: {e}")
            # Fallback: skip captioning, use detection only
            self.caption_model = None
        
        self.loaded = True
        print("[OmniParser] Ready!")
    
    def detect_elements(self, image: Image.Image, conf_threshold: float = 0.3) -> List[Dict]:
        """
        Detect interactable UI elements in screenshot.
        
        Returns list of elements with:
        - id: element index
        - bbox: [x1, y1, x2, y2]
        - center: [x, y]
        - description: what the element is
        - confidence: detection confidence
        """
        if not self.loaded:
            self.load()
        
        start_time = time.time()
        
        # Run YOLO detection
        results = self.icon_detector.predict(
            source=image,
            conf=conf_threshold,
            device='cpu',
            verbose=False
        )
        
        elements = []
        
        for idx, detection in enumerate(results[0].boxes):
            box = detection.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = map(int, box)
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            confidence = float(detection.conf[0])
            
            # Caption the element if model available
            description = "UI element"
            if self.caption_model is not None:
                try:
                    element_img = image.crop((x1, y1, x2, y2))
                    
                    inputs = self.caption_processor(
                        text="<CAPTION>",
                        images=element_img,
                        return_tensors="pt"
                    )
                    
                    with torch.no_grad():
                        output = self.caption_model.generate(
                            **inputs,
                            max_new_tokens=30
                        )
                    
                    description = self.caption_processor.decode(
                        output[0],
                        skip_special_tokens=True
                    ).replace("<CAPTION>", "").strip()
                except:
                    pass
            
            elements.append({
                "id": idx,
                "bbox": [x1, y1, x2, y2],
                "center": [center_x, center_y],
                "description": description,
                "confidence": confidence
            })
        
        elapsed = time.time() - start_time
        print(f"[OmniParser] Detected {len(elements)} elements in {elapsed:.2f}s")
        
        return elements
    
    def annotate_image(self, image: Image.Image, elements: List[Dict]) -> Image.Image:
        """Draw bounding boxes and labels on image."""
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        
        # Try to load a font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            font = ImageFont.load_default()
        
        for elem in elements:
            x1, y1, x2, y2 = elem["bbox"]
            
            # Draw rectangle
            draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
            
            # Draw label
            label = f"[{elem['id']}] {elem['description'][:25]}"
            draw.text((x1, max(0, y1-16)), label, fill="red", font=font)
        
        return annotated


class SmolVLMSelector:
    """
    Stage 2: SmolVLM for action selection.
    Runs on GPU with 4-bit quantization (~4GB VRAM).
    """
    
    def __init__(self, model_path: str = "HuggingFaceTB/SmolVLM-256M-Instruct"):
        self.model_path = model_path
        self.model = None
        self.processor = None
        self.loaded = False
    
    def load(self, quantize: bool = True):
        """Load SmolVLM to GPU with optional quantization."""
        if self.loaded:
            return
        
        print("[SmolVLM] Loading model...")
        
        from transformers import AutoProcessor, AutoModelForVision2Seq, BitsAndBytesConfig
        
        # Load processor
        self.processor = AutoProcessor.from_pretrained(
            self.model_path,
            trust_remote_code=True
        )
        
        # Load model with quantization
        if quantize and torch.cuda.is_available():
            print("[SmolVLM] Using 4-bit quantization for 8GB VRAM")
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
            )
            
            self.model = AutoModelForVision2Seq.from_pretrained(
                self.model_path,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True
            )
        else:
            self.model = AutoModelForVision2Seq.from_pretrained(
                self.model_path,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None,
                trust_remote_code=True
            )
        
        self.loaded = True
        print(f"[SmolVLM] Ready! VRAM: {torch.cuda.memory_allocated()/1024**3:.1f}GB" if torch.cuda.is_available() else "[SmolVLM] Ready (CPU)")
    
    def select_action(
        self, 
        image: Image.Image, 
        elements: List[Dict], 
        instruction: str
    ) -> Dict[str, Any]:
        """
        Select which element to interact with based on instruction.
        
        Returns:
        - action: "click" | "type" | "none"
        - element_id: which element to interact with
        - x, y: click coordinates
        - reasoning: why this element was selected
        """
        if not self.loaded:
            self.load()
        
        start_time = time.time()
        
        # Build structured prompt with detected elements
        elements_text = "\n".join([
            f"[{e['id']}] {e['description']} at ({e['center'][0]}, {e['center'][1]})"
            for e in elements
        ])
        
        prompt = f"""You are a GUI automation assistant. The screen has been analyzed.

Detected UI elements:
{elements_text}

User instruction: {instruction}

Select the element to click. Respond with ONLY the action in this format:
<action>click({{"id": ELEMENT_ID, "x": X_COORD, "y": Y_COORD}})</action>

If no element matches, respond: <action>none</action>"""

        # Process with SmolVLM
        inputs = self.processor(
            images=image,
            text=prompt,
            return_tensors="pt"
        )
        
        if torch.cuda.is_available():
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=100,
                do_sample=False,
                pad_token_id=self.processor.tokenizer.eos_token_id
            )
        
        response = self.processor.decode(outputs[0], skip_special_tokens=True)
        
        elapsed = time.time() - start_time
        print(f"[SmolVLM] Response in {elapsed:.2f}s")
        
        # Parse action
        result = self._parse_response(response, elements)
        result["raw_response"] = response
        result["inference_time"] = elapsed
        
        return result
    
    def _parse_response(self, response: str, elements: List[Dict]) -> Dict:
        """Parse SmolVLM response to extract action."""
        
        # Try to match click action
        click_match = re.search(
            r'<action>click\(\{[^}]*"id":\s*(\d+)[^}]*"x":\s*(\d+)[^}]*"y":\s*(\d+)[^}]*\}\)</action>',
            response
        )
        
        if click_match:
            elem_id = int(click_match.group(1))
            x = int(click_match.group(2))
            y = int(click_match.group(3))
            
            return {
                "action": "click",
                "element_id": elem_id,
                "x": x,
                "y": y
            }
        
        # Try simpler format: click(ID, X, Y)
        simple_match = re.search(r'click\((\d+),\s*(\d+),\s*(\d+)\)', response)
        if simple_match:
            return {
                "action": "click",
                "element_id": int(simple_match.group(1)),
                "x": int(simple_match.group(2)),
                "y": int(simple_match.group(3))
            }
        
        # Try to find any element reference
        elem_ref = re.search(r'\[(\d+)\]', response)
        if elem_ref:
            elem_id = int(elem_ref.group(1))
            if elem_id < len(elements):
                elem = elements[elem_id]
                return {
                    "action": "click",
                    "element_id": elem_id,
                    "x": elem["center"][0],
                    "y": elem["center"][1]
                }
        
        # No action found
        return {"action": "none", "reason": "Could not parse action from response"}


class GUIAutomationAgent:
    """
    Complete two-stage GUI automation pipeline.
    OmniParser (CPU) -> SmolVLM (GPU)
    """
    
    def __init__(self, quantize: bool = True):
        print("="*60)
        print("OmniParser + SmolVLM GUI Automation Agent")
        print("="*60)
        
        self.detector = OmniParserDetector()
        self.selector = SmolVLMSelector()
        
        # Lazy loading - models loaded on first use
        self.quantize = quantize
        self._elements_cache = {}
    
    def parse_screen(self, screenshot: Image.Image) -> Tuple[List[Dict], Image.Image]:
        """Parse screenshot to detect UI elements."""
        elements = self.detector.detect_elements(screenshot)
        annotated = self.detector.annotate_image(screenshot, elements)
        return elements, annotated
    
    def execute(self, screenshot_path: str, instruction: str) -> Dict[str, Any]:
        """
        Full pipeline: detect elements, select action, return coordinates.
        
        Args:
            screenshot_path: Path to screenshot image
            instruction: Natural language instruction (e.g., "Open Chrome")
        
        Returns:
            {
                "action": "click" | "type" | "none",
                "x": int,
                "y": int,
                "element_id": int,
                "elements": [...],
                "annotated_image": PIL.Image
            }
        """
        print(f"\n[Agent] Instruction: {instruction}")
        
        # Load screenshot
        screenshot = Image.open(screenshot_path).convert("RGB")
        
        # Stage 1: Detect UI elements
        elements, annotated = self.parse_screen(screenshot)
        
        if not elements:
            return {
                "action": "none",
                "reason": "No UI elements detected",
                "elements": [],
                "annotated_image": annotated
            }
        
        # Stage 2: Select action
        result = self.selector.select_action(annotated, elements, instruction)
        result["elements"] = elements
        result["annotated_image"] = annotated
        
        if result["action"] == "click":
            print(f"[Agent] Action: click({result['x']}, {result['y']}) - Element [{result['element_id']}]")
        else:
            print(f"[Agent] No action selected")
        
        return result
    
    def execute_click(self, screenshot_path: str, instruction: str) -> Optional[Tuple[int, int]]:
        """Convenience method: returns click coordinates or None."""
        result = self.execute(screenshot_path, instruction)
        
        if result["action"] == "click":
            return (result["x"], result["y"])
        return None


def main():
    parser = argparse.ArgumentParser(description="OmniParser + SmolVLM GUI Agent")
    parser.add_argument("--screenshot", "-s", required=True, help="Screenshot path")
    parser.add_argument("--instruction", "-i", required=True, help="User instruction")
    parser.add_argument("--no-quantize", action="store_true", help="Disable 4-bit quantization")
    parser.add_argument("--save-annotated", help="Save annotated image to path")
    args = parser.parse_args()
    
    # Initialize agent
    agent = GUIAutomationAgent(quantize=not args.no_quantize)
    
    # Execute
    result = agent.execute(args.screenshot, args.instruction)
    
    # Output
    print("\n" + "="*60)
    print("RESULT:")
    print("="*60)
    
    if result["action"] == "click":
        print(f"Action: click")
        print(f"Coordinates: ({result['x']}, {result['y']})")
        print(f"Element: [{result['element_id']}]")
    else:
        print(f"Action: {result['action']}")
        print(f"Reason: {result.get('reason', 'Unknown')}")
    
    print(f"\nDetected {len(result['elements'])} UI elements")
    
    # Save annotated image
    if args.save_annotated:
        result["annotated_image"].save(args.save_annotated)
        print(f"Saved annotated image to: {args.save_annotated}")
    
    # Print JSON result
    output = {
        "action": result["action"],
        "x": result.get("x"),
        "y": result.get("y"),
        "element_id": result.get("element_id"),
        "elements_count": len(result["elements"])
    }
    print(f"\nJSON: {json.dumps(output)}")


if __name__ == "__main__":
    main()
