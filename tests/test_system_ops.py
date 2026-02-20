import sys
import os
import subprocess
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts/kb_backlight.sh'))

def run_cmd(args):
    """Run command and print output."""
    try:
        print(f"Running: {' '.join(args)}")
        res = subprocess.run(args, check=True, capture_output=True, text=True)
        print(f"  ✅ Success. Output: {res.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Failed. Error: {e.stderr.strip()}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def test():
    print("Testing System Operations...")
    
    # 1. File System
    print("\n[FileSystem] Creating Folder...")
    test_dir = os.path.join(os.path.dirname(__file__), "temp_folder_test")
    if os.path.exists(test_dir):
        os.rmdir(test_dir)
    
    try:
        os.mkdir(test_dir)
        if os.path.exists(test_dir):
            print(f"  ✅ Folder created: {test_dir}")
            os.rmdir(test_dir)
            print("  ✅ Folder deleted.")
        else:
            print("  ❌ Folder creation failed.")
    except Exception as e:
        print(f"  ❌ FileSystem Error: {e}")

    # 2. Backlight Control
    print("\n[Backlight] Testing Control...")
    
    # Check if script exists
    if not os.path.exists(SCRIPT_PATH):
        print(f"  ❌ Script not found: {SCRIPT_PATH}")
        return

    # Status
    run_cmd([SCRIPT_PATH, "status"])
    
    # Red
    print("  > Setting Red...")
    run_cmd([SCRIPT_PATH, "color", "FF0000"])
    time.sleep(1)
    
    # Off
    print("  > Turning Off...")
    run_cmd([SCRIPT_PATH, "off"])
    time.sleep(1)
    
    # On
    print("  > Turning On...")
    run_cmd([SCRIPT_PATH, "on"])
    time.sleep(1)
    
    # Blue
    print("  > Setting Blue...")
    run_cmd([SCRIPT_PATH, "color", "0000FF"])

if __name__ == "__main__":
    test()
