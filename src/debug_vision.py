import cv2
import sys
import os

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from capture import ScreenCapture
from detector import YoloDetector

def main():
    print("[*] Initializing Screen Capture...")
    cap = ScreenCapture()
    
    # Parse args for --omni
    model_name = "OmniParser" if "--omni" in sys.argv else "./ui_model.pt"
    
    # Try to load custom model if not omni, fallback to yolov8n
    if model_name != "OmniParser" and not os.path.exists(model_name):
        print(f"[!] {model_name} not found, using 'yolov8n.pt'")
        model_name = "yolov8n.pt"

    print(f"[*] Loading Detector ({model_name})...")
    detector = YoloDetector(model_name)

    print("[*] Capturing screen...")
    screenshot = cap.capture()
    
    print("[*] Running Detection & OCR...")
    detections = detector.detect_and_ocr(screenshot)
    
    print(f"[*] Found {len(detections)} elements.")
    
    # Draw boxes
    output_image = screenshot.copy()
    for i, item in enumerate(detections):
        bbox = item['bbox']
        label = item['label']
        text = item.get('text', '')
        
        x1, y1, x2, y2 = map(int, bbox)
        
        # Color: Green
        color = (0, 255, 0)
        cv2.rectangle(output_image, (x1, y1), (x2, y2), color, 2)
        
        # Label format: "ID: Label (Text)"
        label_str = f"{i}: {label}"
        if text:
            label_str += f"|{text[:10]}"
            
        cv2.putText(output_image, label_str, (x1, y1 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        print(f"    ID {i}: {label} at {bbox} -> '{text}'")

    output_filename = "vision_output.jpg"
    cv2.imwrite(output_filename, output_image)
    print(f"[*] Saved annotated image to: {output_filename}")

if __name__ == "__main__":
    main()
