"""
Test module for Hummingbot integration.
"""

import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import json
import os
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from .hummingbot_client import HummingbotClient

class TestHummingbotClient(unittest.TestCase):
    """Test cases for Hummingbot client."""

    def setUp(self):
        """Set up test cases."""
        self.mock_telegram_bot = Mock()
        self.mock_telegram_bot.send_alert = AsyncMock()
        
        self.config = {
            "hummingbot": {
                "instance_path": "/tmp/hummingbot_test",
                "default_exchange": "binance",
                "default_market": "BTC-USDT"
            },
            "telegram": {
                "bot_token": "test_token",
                "chat_id": "test_chat_id"
            },
            "exchanges": {
                "binance": {
                    "api_key": "test_key",
                    "api_secret": "test_secret"
                }
            },
            "trading": {
                "min_order_size": 0.001,
                "max_order_size": 0.1,
                "stop_loss_pct": 2.0,
                "take_profit_pct": 5.0
            }
        }
        
        self.client = HummingbotClient(self.config, self.mock_telegram_bot)

    def tearDown(self):
        """Clean up after tests."""
        # Remove test directories
        if os.path.exists(self.config['hummingbot']['instance_path']):
            import shutil
            shutil.rmtree(self.config['hummingbot']['instance_path'])

    async def test_setup(self):
        """Test Hummingbot setup."""
        await self.client.setup()
        
        # Check if directories were created
        self.assertTrue(os.path.exists(self.client.config_path))
        self.assertTrue(os.path.exists(self.client.strategy_path))
        self.assertTrue(os.path.exists(self.client.logs_path))
        
        # Check if config files were created
        self.assertTrue(os.path.exists(
            self.client.config_path / 'conf_global.json'
        ))
        self.assertTrue(os.path.exists(
            self.client.config_path / 'conf_strategy_deepseeker.json'
        ))
        self.assertTrue(os.path.exists(
            self.client.strategy_path / 'deepseeker_strategy.py'
        ))

    async def test_start_stop(self):
        """Test starting and stopping Hummingbot."""
        # Mock subprocess.Popen
        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process
            
            # Test start
            await self.client.start()
            self.assertTrue(self.client.running)
            mock_popen.assert_called_once()
            
            # Verify Telegram notification
            self.mock_telegram_bot.send_alert.assert_called_with(
                "🤖 Hummingbot trading started",
                alert_type="general"
            )
            
            # Test stop
            self.mock_telegram_bot.send_alert.reset_mock()
            await self.client.stop()
            self.assertFalse(self.client.running)
            mock_process.terminate.assert_called_once()
            
            # Verify Telegram notification
            self.mock_telegram_bot.send_alert.assert_called_with(
                "🛑 Hummingbot trading stopped",
                alert_type="general"
            )

    def test_parse_trade_event(self):
        """Test trade event parsing."""
        # Test buy event
        buy_log = "2023-01-01 12:00:00 - OrderFilledEvent BUY BTC-USDT 0.1 @ 50000.00"
        buy_result = self.client._parse_trade_event(buy_log)
        
        self.assertIsNotNone(buy_result)
        self.assertEqual(buy_result['type'], 'BUY')
        self.assertEqual(buy_result['symbol'], 'BTC-USDT')
        self.assertEqual(buy_result['amount'], Decimal('0.1'))
        self.assertEqual(buy_result['price'], Decimal('50000.00'))
        
        # Test sell event
        sell_log = "2023-01-01 12:00:00 - OrderFilledEvent SELL BTC-USDT 0.1 @ 51000.00"
        sell_result = self.client._parse_trade_event(sell_log)
        
        self.assertIsNotNone(sell_result)
        self.assertEqual(sell_result['type'], 'SELL')
        self.assertEqual(sell_result['symbol'], 'BTC-USDT')
        self.assertEqual(sell_result['amount'], Decimal('0.1'))
        self.assertEqual(sell_result['price'], Decimal('51000.00'))
        
        # Test invalid event
        invalid_log = "2023-01-01 12:00:00 - Some other event"
        invalid_result = self.client._parse_trade_event(invalid_log)
        self.assertIsNone(invalid_result)

    async def test_notify_trade(self):
        """Test trade notifications."""
        trade_details = {
            'type': 'BUY',
            'symbol': 'BTC-USDT',
            'amount': Decimal('0.1'),
            'price': Decimal('50000.00'),
            'timestamp': datetime.now()
        }
        
        await self.client._notify_trade(trade_details)
        
        self.mock_telegram_bot.send_alert.assert_called_once()
        call_args = self.mock_telegram_bot.send_alert.call_args[0]
        message = call_args[0]
        
        self.assertIn('BUY Order Filled', message)
        self.assertIn('BTC-USDT', message)
        self.assertIn('0.10000000', message)
        self.assertIn('$50000.00', message)
        self.assertIn('$5000.00', message)  # Total value

    async def test_process_log_line(self):
        """Test log line processing."""
        # Test trade event
        trade_log = "2023-01-01 12:00:00 - OrderFilledEvent BUY BTC-USDT 0.1 @ 50000.00"
        await self.client._process_log_line(trade_log)
        
        self.mock_telegram_bot.send_alert.assert_called_once()
        self.mock_telegram_bot.send_alert.reset_mock()
        
        # Test error event
        error_log = "2023-01-01 12:00:00 - ERROR Something went wrong"
        await self.client._process_log_line(error_log)
        
        self.mock_telegram_bot.send_alert.assert_called_once()
        call_args = self.mock_telegram_bot.send_alert.call_args[0]
        self.assertIn('Error', call_args[0])

    def test_config_generation(self):
        """Test configuration file generation."""
        async def run_test():
            await self.client.setup()
            
            # Check global config
            with open(self.client.config_path / 'conf_global.json') as f:
                global_config = json.load(f)
                
            self.assertEqual(global_config['instance_id'], 'deepseeker_bot')
            self.assertTrue(global_config['kill_switch_enabled'])
            self.assertEqual(global_config['telegram_token'], 
                           self.config['telegram']['bot_token'])
            
            # Check strategy config
            with open(self.client.config_path / 'conf_strategy_deepseeker.json') as f:
                strategy_config = json.load(f)
                
            self.assertEqual(strategy_config['strategy'], 'deepseeker_strategy')
            self.assertEqual(strategy_config['exchange'], 
                           self.config['hummingbot']['default_exchange'])
            self.assertEqual(strategy_config['min_order_size'],
                           self.config['trading']['min_order_size'])
        
        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
