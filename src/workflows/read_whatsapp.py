
import sys
import os
import argparse
import json

# Add parent dir to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.bridges.whatsapp_bridge import WhatsAppBridge

def main():
    parser = argparse.ArgumentParser(description="Read WhatsApp messages via Electron Bridge")
    parser.add_argument("--limit", type=int, default=10, help="Number of chats/messages to read")
    args = parser.parse_args()

    # Initialize Bridge
    bridge = WhatsAppBridge()
    
    if not bridge.connect():
        print("[-] Failed to connect to WhatsApp Bridge.")
        sys.exit(1)
        
    print("[*] Bridge connected. Reading messages...")
    
    # 1. Get Chat List Snippets (History)
    chats = bridge.get_messages(limit=args.limit)
    
    # 2. Get Active Chat Messages (Context)
    active_chat = bridge.get_active_chat_messages()
    
    output = {
        "status": "success", 
        "chat_list": chats,
        "active_chat_context": active_chat or []
    }
    
    print(f"\n[+] Parsed {len(chats)} chats.")
    if active_chat:
        print(f"[+] Active Chat Context: {len(active_chat)} messages.")
        
    # Print JSON for Brain to consume
    print("---JSON_START---")
    print(json.dumps(output, indent=2))
    print("---JSON_END---")
    
    bridge.close()

if __name__ == "__main__":
    main()
