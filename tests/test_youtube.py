import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

def test():
    print("Testing YouTube Playback (pywhatkit)...")
    try:
        import pywhatkit
        print("✅ pywhatkit imported successfully.")
        
        query = "Rick Astley Never Gonna Give You Up"
        print(f"▶️ Playing: {query}")
        print("(This should open a browser tab)")
        
        # pywhatkit.playonyt opens the URL in the default browser
        pywhatkit.playonyt(query)
        
        print("✅ Command executed.")
    except ImportError:
        print("❌ pywhatkit not installed.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test()
