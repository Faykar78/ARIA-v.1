import os
import json
from datasets import load_dataset

DATASET_NAME = "xlangai/ubuntu_osworld_verified_trajs"
OUTPUT_DIR = "./training_data/raw"

def download_and_inspect():
    print(f"[*] Loading dataset (Streaming Mode): {DATASET_NAME}...")
    try:
        # STREAMING MODE to avoid 200GB download
        # We will only take the first 50 episodes
        dataset = load_dataset(DATASET_NAME, split="train", streaming=True)
        
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        count = 0
        limit = 50 # User requested a small sample (~5 files worth equivalent)
        
        print(f"[*] Downloading first {limit} episodes...")
        
        for i, episode in enumerate(dataset):
            if i >= limit:
                break
                
            episode_id = episode.get("id", f"ep_{i}")
            save_path = os.path.join(OUTPUT_DIR, f"{episode_id}.json")
            
            # Save individual episode
            with open(save_path, "w") as f:
                json.dump(episode, f, indent=2, default=str)
            
            count += 1
            if count % 5 == 0:
                print(f"    -> Saved {count}/{limit} episodes...")
                
        print(f"[*] Sample Download Complete. Saved {count} episodes to {OUTPUT_DIR}")
        return True
        
    except Exception as e:
        print(f"[!] Error downloading dataset: {e}")
        return None

if __name__ == "__main__":
    download_and_inspect()
