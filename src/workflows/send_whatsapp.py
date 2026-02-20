
import sys
import os
import argparse

# Add parent dir to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.bridges.whatsapp_bridge import WhatsAppBridge

def main():
    parser = argparse.ArgumentParser(description="Send WhatsApp message via Browser WhatsApp Web")
    parser.add_argument("--contact", type=str, required=True, help="Contact name to send message to")
    parser.add_argument("--message", type=str, required=True, help="Message content to send")
    args = parser.parse_args()

    # Initialize Bridge (connects to browser)
    bridge = WhatsAppBridge()
    
    if not bridge.connect():
        print("[-] Failed to connect to WhatsApp Web in browser.")
        print("[!] Make sure WhatsApp Web is open in Chrome (via 'open whatsapp' command)")
        sys.exit(1)
        
    print(f"[*] Bridge connected to WhatsApp Web.")
    
    # 1. Select Chat
    print(f"[*] Searching for contact: {args.contact}")
    if not bridge.select_chat(args.contact):
        print(f"[-] Failed to select chat '{args.contact}'")
        bridge.close()
        sys.exit(1)
    
    # 2. Send Message
    print(f"[*] Sending message: '{args.message}'")
    if bridge.send_message(args.message):
        print(f"[+] Message sent successfully to {args.contact}!")
    else:
        print(f"[-] Failed to send message.")
        bridge.close()
        sys.exit(1)
    
    bridge.close()
    print("[+] Done.")

if __name__ == "__main__":
    main()
