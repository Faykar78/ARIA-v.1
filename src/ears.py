import json
import os
import sys
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Ears:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = os.path.join(_PROJECT_DIR, "models", "vosk-model-small-en-us-0.15")
        self.model_path = model_path
        if not os.path.exists(self.model_path):
            print(f"[!] Vosk model not found at {self.model_path}")
            print("    Please run download_voice.py")
            self.model = None
            return

        print(f"[*] Loading Ears ({model_path})...")
        try:
            self.model = Model(self.model_path)
            self.q = queue.Queue()
        except Exception as e:
            print(f"[!] Error loading Vosk: {e}")
            self.model = None

    def listen_once(self, timeout=7):
        """Listens for a single command. Returns text or None if timeout."""
        if not self.model:
            return input("Enter command (Voice disabled): ")

        print(f"[*] Listening... (You have {timeout}s to speak)")
        
        with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                               channels=1, callback=self._callback):
            rec = KaldiRecognizer(self.model, 16000)
            start_time = None
            
            while True:
                try:
                    # Non-blocking get with short timeout to allow checking overall timeout
                    data = self.q.get(timeout=1.0)
                    if rec.AcceptWaveform(data):
                        res = json.loads(rec.Result())
                        text = res.get("text", "")
                        if text:
                            print(f"    -> Heard: '{text}'")
                            return text
                except queue.Empty:
                    pass
                
                # Check overall timeout logic could be fancier (actual time check) -- 
                # strictly speaking Queue.get(timeout) is per-chunk. 
                # Let's just rely on upstream handling or user interruption for now
                # Actually, implementing a real timeout return:
                import time
                if start_time is None: start_time = time.time()
                if time.time() - start_time > timeout:
                    return None

    def _callback(self, indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            print(status, file=sys.stderr)
        self.q.put(bytes(indata))

if __name__ == "__main__":
    e = Ears()
    if e.model:
        print("Say something!")
        print(f"Result: {e.listen_once()}")
