import cv2
import sys
import os
# from ultralytics import YOLO # REMOVED per user request

class BaseDetector:
    def __init__(self):
        print("[*] Detector initialized (Vision Disabled/YOLO Removed).")

    def detect(self, image, conf=0.25):
        return []

    def detect_and_ocr(self, image, conf=0.25):
        # Return empty list or implement alternative (e.g. pure OCR, or VLM)
        return []

if __name__ == "__main__":
    print("Detector test (Empty)")
