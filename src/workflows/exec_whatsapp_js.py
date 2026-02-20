
import sys
import os
import argparse
import json

# Add parent dir to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.bridges.whatsapp_bridge import WhatsAppBridge

def main():
    parser = argparse.ArgumentParser(description="Execute raw JS in WhatsApp Electron")
    parser.add_argument("--js", required=True, help="JavaScript code to execute")
    args = parser.parse_args()

    # Initialize Bridge
    bridge = WhatsAppBridge()
    
    if not bridge.connect():
        print("[-] Failed to connect to WhatsApp Bridge.")
        sys.exit(1)
        
    print(f"[*] Executing JS: {args.js}")
    
    try:
        # We use evaluate logic
        # Wrap in IIFE if needed, but bridge evaluates expression
        result = bridge.page.evaluate(args.js)
        print("---RESULT_START---")
        print(json.dumps(result, default=str)) # Handle non-serializable
        print("---RESULT_END---")
    except Exception as e:
        print(f"[-] Execution failed: {e}")
        sys.exit(1)
    finally:
        bridge.close()

if __name__ == "__main__":
    main()
