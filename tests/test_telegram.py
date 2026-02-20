import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.bridges.telegram_bridge import telegram_bridge

async def test():
    print("Testing Telegram Bridge...")
    
    # 1. Check Token
    if telegram_bridge.token == "YOUR_TOKEN_HERE":
        print("✅ Correctly identified placeholder token.")
    else:
        print(f"❓ Token is set to: {telegram_bridge.token}")

    # 2. Try Init
    success = await telegram_bridge.initialize()
    if not success:
        print("✅ Initialize returned False (as expected with placeholder).")
    else:
        print("❌ Initialize returned True unexpectedly.")

    # 3. Try Send
    res = await telegram_bridge.send_message("123", "test")
    if not res['success']:
        print(f"✅ Send failed gracefully: {res['error']}")
    else:
        print("❌ Send succeeded unexpectedly.")

if __name__ == "__main__":
    asyncio.run(test())
