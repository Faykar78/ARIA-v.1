import asyncio
import logging
from telegram import Bot
from telegram.error import TelegramError

# ==============================================================================
# 🔒 SECURITY CONFIGURATION
# ==============================================================================
# PASTE YOUR TELEGRAM BOT TOKEN BELOW
TELEGRAM_BOT_TOKEN = "6682525375:AAEboG4iowZt-uGJ0nv-tIXNq9VQgqoz6X8" 
# ==============================================================================

logger = logging.getLogger(__name__)

class TelegramBridge:
    def __init__(self, token=None):
        """
        Initialize the Telegram Bridge.
        If token is provided, it overrides the global configuration.
        """
        self.token = token if token else TELEGRAM_BOT_TOKEN
        self.bot = None
        self.last_update_id = 0
        
        # Check if token is the default placeholder
        #if self.token == "6682525375:AAEboG4iowZt-uGJ0nv-tIXNq9VQgqoz6X8" or not self.token:
        #    logger.warning("⚠️  Telegram Bot Token not configured in src/bridges/telegram_bridge.py")
         #   print("⚠️  [Telegram] Token not set. Please edit src/bridges/telegram_bridge.py")

    async def initialize(self):
        """Initializes the bot instance."""
        if not self.token or self.token == "6682525375:AAEboG4iowZt-uGJ0nv-tIXNq9VQgqoz6X8":
            return False
            
        try:
            self.bot = Bot(token=self.token)
            me = await self.bot.get_me()
            logger.info(f"✅ Telegram Bot connected: @{me.username}")
            print(f"    [Telegram] Connected as @{me.username}")
            return True
        except Exception as e:
            logger.error(f"❌ Telegram Connection Error: {e}")
            print(f"    [Telegram] Connection Failed: {e}")
            return False

    async def send_message(self, chat_id: str, text: str):
        """Sends a text message to a specific chat ID."""
        if not self.bot:
            if not await self.initialize():
                return {"success": False, "error": "Bot token not configured"}

        try:
            await self.bot.send_message(chat_id=chat_id, text=text)
            return {"success": True}
        except TelegramError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": f"Unknown error: {e}"}

    async def get_recent_messages(self, limit=5):
        """
        Fetches recent messages using long polling (get_updates).
        In a real production bot you might use webhooks, but polling is easier for local dev.
        """
        if not self.bot:
            if not await self.initialize():
                return []

        try:
            updates = await self.bot.get_updates(offset=self.last_update_id + 1, limit=limit, timeout=1)
            messages = []
            for update in updates:
                self.last_update_id = update.update_id
                if update.message and update.message.text:
                    messages.append({
                        "id": update.message.message_id,
                        "chat_id": update.message.chat.id,
                        "sender": update.message.from_user.username or update.message.from_user.first_name,
                        "text": update.message.text,
                        "date": update.message.date.isoformat()
                    })
            return messages
        except Exception as e:
            logger.error(f"Error fetching updates: {e}")
            return []

# Singleton instance for easy import
telegram_bridge = TelegramBridge()
