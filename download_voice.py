import os
import requests
import zipfile
import io

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODELS_DIR = "./models"
EXTRACT_PATH = os.path.join(MODELS_DIR, "vosk-model-small-en-us-0.15")

os.makedirs(MODELS_DIR, exist_ok=True)

def download_vosk():
    if os.path.exists(EXTRACT_PATH):
        print(f"[*] Vosk model already exists at {EXTRACT_PATH}")
        return

    print(f"[*] Downloading Vosk Model from {MODEL_URL}...")
    try:
        r = requests.get(MODEL_URL)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(MODELS_DIR)
        print(f" -> Extracted to {EXTRACT_PATH}")
    except Exception as e:
        print(f"[!] Error downloading/extracting Vosk: {e}")

if __name__ == "__main__":
    download_vosk()
