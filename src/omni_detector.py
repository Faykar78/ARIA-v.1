
import sys
import os
import torch
import numpy as np
import base64
import io
from PIL import Image

# Add OmniParser to path so we can import util.utils
OMNIPARSER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../OmniParser")
sys.path.append(OMNIPARSER_DIR)

try:
    from util.utils import get_yolo_model, get_caption_model_processor, get_som_labeled_img, check_ocr_box
except ImportError as e:
    print(f"[!] Error importing OmniParser utils: {e}")
    # Fallback or error handling
    raise

class OmniDetector:
    def __init__(self, weights_dir=None):
        if weights_dir is None:
            weights_dir = os.path.join(OMNIPARSER_DIR, "weights")
            
        print("[*] Initializing OmniParser V2...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"    - Device: {self.device}")
        
        # Paths
        yolo_path = os.path.join(weights_dir, "icon_detect", "model.pt")
        caption_path = os.path.join(weights_dir, "icon_caption_florence")
        
        # Load Models
        print(f"    - Loading YOLO: {yolo_path}")
        self.yolo_model = get_yolo_model(yolo_path)
        
        print(f"    - Loading Caption: {caption_path}")
        self.caption_model_processor = get_caption_model_processor("florence2", caption_path, device=self.device)
        print("[*] OmniParser Models Loaded.")

    def detect(self, image_input):
        """
        Main entry point for detection and OCR.
        Returns coordinate string or structured list.
        """
        # Convert input to PIL Image
        if isinstance(image_input, np.ndarray):
            image_pil = Image.fromarray(image_input)
        elif isinstance(image_input, str): # Path
            image_pil = Image.open(image_input)
        else:
            image_pil = image_input
            
        if image_pil.mode == 'RGBA':
            image_pil = image_pil.convert('RGB')

        # 1. ORC Phase using check_ocr_box (uses PaddleOCR by default in V2 demo)
        # Note: We need accurate text.
        # check_ocr_box returns (text, box_list), goal_filtering
        # We'll use defaults similar to demo
        print("    [Omni] Running OCR...")
        (text, ocr_bbox), _ = check_ocr_box(
            image_pil, 
            display_img=False, 
            output_bb_format='xyxy', 
            goal_filtering=None, 
            easyocr_args={'paragraph': False, 'text_threshold': 0.9},
            use_paddleocr=False 
        )
        
        # 2. OmniParser Phase (Icon Detect + Caption + Merge)
        print("    [Omni] Running Icon Detection & Captioning...")
        box_overlay_ratio = max(image_pil.size) / 3200
        draw_bbox_config = {
            'text_scale': 0.8 * box_overlay_ratio,
            'text_thickness': max(int(2 * box_overlay_ratio), 1),
            'text_padding': max(int(3 * box_overlay_ratio), 1),
            'thickness': max(int(3 * box_overlay_ratio), 1),
        }
        
        dino_labled_img, label_coordinates, parsed_content_list = get_som_labeled_img(
            image_pil, 
            self.yolo_model,
            BOX_TRESHOLD=0.05, 
            output_coord_in_ratio=False, # We want absolute pixels for mapping
            ocr_bbox=ocr_bbox,
            draw_bbox_config=draw_bbox_config,
            caption_model_processor=self.caption_model_processor,
            ocr_text=text,
            use_local_semantics=True, 
            iou_threshold=0.7, 
            scale_img=False, 
            batch_size=64 # Reduced batch size for safety
        )
        
        # 3. Format Output
        # parsed_content_list is a list of dicts: {'bbox': [x1,y1,x2,y2], 'content': 'text', 'type': 'icon'/'text'}
        # We need to map this to our agent's expected format if needed, but for now returned list ensures
        # we have all elements.
        
        # Convert to list of detected items
        detected_items = []
        for i, item in enumerate(parsed_content_list):
            bbox = item.get('bbox') # [x1, y1, x2, y2]
            content = item.get('content', '')
            item_type = item.get('type', 'element')
            source = item.get('source', '')
            
            # Label construction
            # If it comes from OCR, content is the text.
            # If icon, content is caption.
            label = content if content else "unknown"
            
            detected_items.append({
                'label': item_type,
                'bbox': bbox,
                'text': content,
                'id': i
            })
            
        print(f"    [Omni] Detected {len(detected_items)} elements.")
        return detected_items, dino_labled_img

if __name__ == "__main__":
    # Test run
    det = OmniDetector()
    # Dummy image test if args provided
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
        print(f"Testing on {img_path}")
        items, _ = det.detect(img_path)
        for item in items:
            print(item)
