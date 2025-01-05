"""
Test module for Telegram bot functionality.
"""

import unittest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from decimal import Decimal
from telegram import Update, Chat, Message, User
from telegram.ext import CallbackContext
from .telegram_bot import TelegramBot

class TestTelegramBot(unittest.TestCase):
    """Test cases for Telegram bot functionality."""

    def setUp(self):
        """Set up test cases."""
        self.mock_filter_manager = Mock()
        self.mock_profit_loss_tracker = Mock()
        self.mock_profit_loss_tracker.get_performance_summary = AsyncMock()
        
        self.bot = TelegramBot(
            token="test_token",
            filter_manager=self.mock_filter_manager,
            profit_loss_tracker=self.mock_profit_loss_tracker
        )
        
        # Mock update object
        self.mock_user = User(id=1, is_bot=False, first_name="Test", username="test_user")
        self.mock_chat = Chat(id=1, type="private")
        self.mock_message = Message(
            message_id=1,
            date=datetime.now(),
            chat=self.mock_chat,
            from_user=self.mock_user
        )
        self.mock_update = Update(update_id=1, message=self.mock_message)
        
        # Mock context
        self.mock_context = Mock(spec=CallbackContext)

    async def test_start_command(self):
        """Test the start command."""
        self.mock_message.reply_text = AsyncMock()
        
        await self.bot.start_command(self.mock_update, self.mock_context)
        
        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args[0][0]
        self.assertIn("Welcome to DeepSeeker Bot", call_args)
        self.assertIn("/subscribe", call_args)

    async def test_help_command(self):
        """Test the help command."""
        self.mock_message.reply_text = AsyncMock()
        
        await self.bot.help_command(self.mock_update, self.mock_context)
        
        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args[0][0]
        self.assertIn("DeepSeeker Bot Commands", call_args)
        self.assertIn("Filter Management", call_args)

    async def test_subscribe_command(self):
        """Test the subscribe command."""
        self.mock_message.reply_text = AsyncMock()
        
        # Test new subscription
        await self.bot.subscribe_command(self.mock_update, self.mock_context)
        
        self.mock_message.reply_text.assert_called_once()
        self.assertIn(self.mock_chat.id, self.bot.alert_subscribers)
        call_args = self.mock_message.reply_text.call_args[0][0]
        self.assertIn("subscribed", call_args.lower())
        
        # Test already subscribed
        self.mock_message.reply_text.reset_mock()
        await self.bot.subscribe_command(self.mock_update, self.mock_context)
        
        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args[0][0]
        self.assertIn("already subscribed", call_args.lower())

    async def test_unsubscribe_command(self):
        """Test the unsubscribe command."""
        self.mock_message.reply_text = AsyncMock()
        
        # Add subscriber first
        self.bot.alert_subscribers.add(self.mock_chat.id)
        
        # Test unsubscribe
        await self.bot.unsubscribe_command(self.mock_update, self.mock_context)
        
        self.mock_message.reply_text.assert_called_once()
        self.assertNotIn(self.mock_chat.id, self.bot.alert_subscribers)
        call_args = self.mock_message.reply_text.call_args[0][0]
        self.assertIn("unsubscribed", call_args.lower())
        
        # Test already unsubscribed
        self.mock_message.reply_text.reset_mock()
        await self.bot.unsubscribe_command(self.mock_update, self.mock_context)
        
        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args[0][0]
        self.assertIn("not currently subscribed", call_args.lower())

    async def test_status_command(self):
        """Test the status command."""
        self.mock_message.reply_text = AsyncMock()
        self.mock_filter_manager.get_current_filters.return_value = {'min_liquidity': 1000}
        self.mock_filter_manager.get_blacklist.return_value = ['0x123', '0x456']
        
        await self.bot.status_command(self.mock_update, self.mock_context)
        
        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args[0][0]
        self.assertIn("DeepSeeker Bot Status", call_args)
        self.assertIn("Active Filters: 1", call_args)
        self.assertIn("Blacklisted Addresses: 2", call_args)

    async def test_performance_command(self):
        """Test the performance command."""
        self.mock_profit_loss_tracker.get_performance_summary.return_value = {
            'total_realized_pnl': 1000.0,
            'total_trades': 10,
            'winning_trades': 7,
            'win_rate': 70.0,
            'average_pnl_per_trade': 100.0
        }
        
        self.bot.application = Mock()
        self.bot.application.bot.send_message = AsyncMock()
        
        await self.bot.performance_command(self.mock_update, self.mock_context)
        
        self.bot.application.bot.send_message.assert_called_once()
        call_args = self.bot.application.bot.send_message.call_args[0][1]
        self.assertIn("Trading Performance Report", call_args)
        self.assertIn("$1,000.00", call_args)
        self.assertIn("70.0%", call_args)

    async def test_send_alert(self):
        """Test sending alerts."""
        self.bot.application = Mock()
        self.bot.application.bot.send_message = AsyncMock()
        
        # Add a subscriber
        self.bot.alert_subscribers.add(self.mock_chat.id)
        
        # Test different alert types
        alert_types = {
            "general": "ℹ️",
            "rugpull": "🚨",
            "pump": "📈",
            "cex": "📱",
            "performance": "📊"
        }
        
        for alert_type, emoji in alert_types.items():
            await self.bot.send_alert("Test message", alert_type)
            
            self.bot.application.bot.send_message.assert_called()
            call_args = self.bot.application.bot.send_message.call_args[0][1]
            self.assertIn(emoji, call_args)
            self.assertIn("Test message", call_args)
            
            self.bot.application.bot.send_message.reset_mock()

    async def test_periodic_performance_report(self):
        """Test periodic performance report."""
        self.bot.application = Mock()
        self.bot.application.bot.send_message = AsyncMock()
        self.mock_profit_loss_tracker.get_performance_summary.return_value = {
            'total_realized_pnl': 1000.0,
            'total_trades': 10,
            'winning_trades': 7,
            'win_rate': 70.0,
            'average_pnl_per_trade': 100.0
        }
        
        # Add a subscriber
        self.bot.alert_subscribers.add(self.mock_chat.id)
        
        # Set last report to trigger immediate report
        self.bot.last_performance_report = datetime.now() - timedelta(hours=25)
        
        # Run one iteration
        try:
            await asyncio.wait_for(
                self.bot.periodic_performance_report(),
                timeout=1
            )
        except asyncio.TimeoutError:
            pass
        
        self.bot.application.bot.send_message.assert_called_once()
        call_args = self.bot.application.bot.send_message.call_args[0][1]
        self.assertIn("Trading Performance Report", call_args)
        self.assertIn("$1,000.00", call_args)

if __name__ == '__main__':
    unittest.main()
