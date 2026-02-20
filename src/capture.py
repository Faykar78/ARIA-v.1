
import mss
import numpy as np
import cv2

class ScreenCapture:
    def __init__(self):
        self.sct = mss.mss()
        # Select primary monitor (index 1 in mss)
        # Index 0 is "All monitors combined"
        if len(self.sct.monitors) > 1:
            self.monitor = self.sct.monitors[1]
        else:
            self.monitor = self.sct.monitors[0]

    def capture(self):
        """Captures the screen and returns a BGR numpy array (OpenCV format)."""
        screenshot = self.sct.grab(self.monitor)
        img = np.array(screenshot)
        # MSS returns BGRA, convert to BGR
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def get_resolution(self):
        return (self.monitor["width"], self.monitor["height"])
