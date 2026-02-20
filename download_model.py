from huggingface_hub import hf_hub_download, list_repo_files
import shutil
import os

def download_model():
    repo_id = "macpaw-research/yolov11l-ui-elements-detection"
    print(f"Listing files in {repo_id}...")
    
    try:
        files = list_repo_files(repo_id=repo_id)
        pt_files = [f for f in files if f.endswith('.pt')]
        
        if not pt_files:
            print("No .pt files found in the repo!")
            return

        # Pick the first one, or prefer one that looks like a weight file
        target_file = pt_files[0]
        print(f"Found model file: {target_file}")
        
        print(f"Downloading {target_file}...")
        model_path = hf_hub_download(repo_id=repo_id, filename=target_file)
        
        target_path = "ui_model.pt"
        shutil.copy(model_path, target_path)
        print(f"Success! Model saved to {os.path.abspath(target_path)}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    download_model()
