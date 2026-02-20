
import os
import sys
import io
import base64
import torch
import json
from PIL import Image

# Add OmniParser to path
POSSIBLE_PATHS = [
    os.path.expanduser("~/home/llama.cpp"), # User specified
    os.path.expanduser("~/llama.cpp"),      # Common variant
    os.path.abspath(os.path.join(os.path.dirname(__file__), '../OmniParser')) # Local fallback
]

OMNI_PARSER_DIR = None
for path in POSSIBLE_PATHS:
    if os.path.exists(os.path.join(path, "util", "utils.py")):
        OMNI_PARSER_DIR = path
        break

if OMNI_PARSER_DIR:
    if OMNI_PARSER_DIR not in sys.path:
        sys.path.append(OMNI_PARSER_DIR)
    print(f"[*] Found OmniParser at: {OMNI_PARSER_DIR}")
else:
    print("[!] Warning: OmniParser not found in expected paths.")

# Import OmniParser Utils
try:
    from util.utils import (
        get_yolo_model, 
        get_caption_model_processor, 
        check_ocr_box, 
        get_som_labeled_img
    )
except ImportError as e:
    print(f"[!] Error importing OmniParser: {e}")
    print(f"    Existing Paths: {sys.path}")
    raise e

class OmniParserClient:
    def __init__(self, device="cuda"):
        self.device = device if torch.cuda.is_available() else "cpu"
        print(f"[*] Initializing OmniParser Client on {self.device}...")
        
        # Load Weights
        yolo_path = os.path.join(OMNI_PARSER_DIR, 'weights/icon_detect/model.pt')
        caption_path = os.path.join(OMNI_PARSER_DIR, 'weights/icon_caption_florence')
        
        print(f"    - Loading YOLO from {yolo_path}")
        self.yolo_model = get_yolo_model(model_path=yolo_path)
        
        print(f"    - Loading Caption Model from {caption_path}")
        self.caption_model_processor = get_caption_model_processor(
            model_name="florence2", 
            model_name_or_path=caption_path, 
            device=self.device
        )
        print("[+] OmniParser Initialized.")

    def parse(self, image_path, box_threshold=0.05, iou_threshold=0.1):
        """
        Parses the screen image.
        Returns:
            - labeled_image (PIL Image): Image with IDs drawn.
            - parsed_items (List[Dict]): Structured list of elements {id, label, text, bbox}
        """
        image_input = Image.open(image_path).convert("RGB")
        imgsz = 640 # Default size
        
        # 1. OCR Step
        ocr_bbox_rslt, _ = check_ocr_box(
            image_input, 
            display_img=False, 
            output_bb_format='xyxy', 
            goal_filtering=None, 
            easyocr_args={'paragraph': False, 'text_threshold': 0.9}, 
            use_paddleocr=False # PaddleOCR failing on cuDNN
        )
        text, ocr_bbox = ocr_bbox_rslt
        
        # 2. Set-of-Mark Labeling
        draw_bbox_config = {
            'text_scale': 0.8,
            'text_thickness': 2,
            'text_padding': 3,
            'thickness': 3,
        }
        
        encoded_img, label_coordinates, filtered_items = get_som_labeled_img(
            image_input, 
            self.yolo_model, 
            BOX_TRESHOLD=box_threshold, 
            output_coord_in_ratio=False, # We want pixels for clicking
            ocr_bbox=ocr_bbox,
            draw_bbox_config=draw_bbox_config,
            caption_model_processor=self.caption_model_processor,
            ocr_text=text,
            iou_threshold=iou_threshold,
            imgsz=imgsz
        )
        
        # Decode Base64 image back to PIL
        labeled_image = Image.open(io.BytesIO(base64.b64decode(encoded_img)))
        
        # 3. Format Output for Brain
        # Logic matches util/utils.py construction of IDs
        # filtered_items contains dictionaries with 'content' (description) and 'bbox'
        # We need to map them to the numeric IDs used in label_coordinates/labeled_image
        
        # Note: util.utils constructs IDs based on index.
        parsed_items = []
        for i, item in enumerate(filtered_items):
            # OmniParser Utils Logic:
            # If item content was None (icon), it was filled by caption model.
            # ID seems to be just the index 'i' in the final filtered list?
            # Let's verify against get_som_labeled_img logic.
            # Yes, phrases = [str(i) for i in range(len(filtered_boxes))]
            
            label_text = item.get('content', 'Unknown')
            bbox = item.get('bbox', [0,0,0,0]) # [x1, y1, x2, y2] (Normalized 0-1)
            
            # De-normalize to pixels
            w, h = image_input.size
            pixel_bbox = [
                int(bbox[0] * w),
                int(bbox[1] * h),
                int(bbox[2] * w),
                int(bbox[3] * h)
            ]
            
            parsed_items.append({
                "id": i,
                "label": "element", # Generic class
                "text": label_text,
                "box_2d": pixel_bbox 
            })
            
        return labeled_image, parsed_items

    def ground(self, image_path, query):
        """
        Uses Florence-2 to find specific elements by description (Phrase Grounding).
        Acts as a 'Vision Projector' for Llama.
        """
        image_input = Image.open(image_path).convert("RGB")
        
        # Access internals
        model = self.caption_model_processor['model']
        processor = self.caption_model_processor['processor']
        device = model.device

        # Construct Prompt for Grounding
        prompt = f"<CAPTION_TO_PHRASE_GROUNDING> {query}"
        
        inputs = processor(text=prompt, images=image_input, return_tensors="pt").to(device)
        # Cast pixels to model's precision (float16) to avoid RuntimeError
        if model.dtype != inputs["pixel_values"].dtype:
            inputs["pixel_values"] = inputs["pixel_values"].to(model.dtype)
        
        # Generate
        with torch.no_grad():
            generated_ids = model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                early_stopping=False,
                do_sample=False,
                num_beams=3,
            )
        
        generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
        
        # Parse Response
        # Florence-2 returns formatted string, processor has a helper to parse it
        parsed_answer = processor.post_process_generation(
            generated_text, 
            task="<CAPTION_TO_PHRASE_GROUNDING>", 
            image_size=(image_input.width, image_input.height)
        )
        
        # Structure: {'<CAPTION_TO_PHRASE_GROUNDING>': {'bboxes': [[x1, y1, x2, y2]], 'labels': ['query']}}
        result = parsed_answer.get('<CAPTION_TO_PHRASE_GROUNDING>', {})
        bboxes = result.get('bboxes', [])
        
        if bboxes:
            # Return center of first match
            bbox = bboxes[0] # [x1, y1, x2, y2]
            return bbox
        else:
            return None

if __name__ == "__main__":
    # Test run
    client = OmniParserClient()
    # Assume a test image exists or take one?
    # client.parse("test.png")
