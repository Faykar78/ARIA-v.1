import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.bridges.email_bridge import email_bridge

def test():
    print("Testing Email Bridge...")
    
    # 1. Check Config
    if not email_bridge._is_configured():
        print("❌ Email Config Missing. Please edit src/bridges/email_bridge.py")
        return

    print("✅ Configuration found.")

    # 2. Test IMAP (Read)
    print("\n[IMAP] Connecting to Inbox...")
    res = email_bridge.read_emails(limit=1, unread_only=False)
    if res['success']:
        print(f"✅ Connection Successful. Found {res['count']} emails.")
        if res['count'] > 0:
            last = res['emails'][0]
            print(f"   Subject: {last['subject']}")
            print(f"   From:    {last['from']}")
    else:
        print(f"❌ IMAP Failed: {res.get('error')}")

    # 3. Test SMTP (Send) - Self Test
    print("\n[SMTP] Sending self-test email...")
    my_email = email_bridge.config["email"]
    res = email_bridge.send_email(my_email, "ARIA Test", "This is a test email from your ARIA agent.")
    if res['success']:
        print("✅ Email Sent Successfully!")
    else:
        print(f"❌ SMTP Failed: {res.get('error')}")

if __name__ == "__main__":
    test()
