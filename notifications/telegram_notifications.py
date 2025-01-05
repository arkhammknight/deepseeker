"""
Telegram notifications module.
"""

import logging
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Handles Telegram notifications."""
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize TelegramNotifier.

        Args:
            bot_token: Telegram bot token
            chat_id: Target chat ID
        """
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id

    async def send_notification(
        self,
        message: str,
        parse_mode: Optional[str] = None
    ) -> bool:
        """
        Send notification via Telegram.

        Args:
            message: Message to send
            parse_mode: Optional parse mode (HTML/Markdown)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send Telegram notification: {str(e)}")
            return False

    async def send_alert(
        self,
        message: str,
        alert_type: str = "general"
    ) -> bool:
        """
        Send alert with specific type.

        Args:
            message: Alert message
            alert_type: Type of alert (general/warning/error)

        Returns:
            bool: True if successful, False otherwise
        """
        # Add emoji based on alert type
        emoji_map = {
            "general": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅"
        }
        
        emoji = emoji_map.get(alert_type, "ℹ️")
        formatted_message = f"{emoji} {message}"
        
        return await self.send_notification(formatted_message)
