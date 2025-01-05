"""
End-to-end test suite for DeepSeeker Bot.

This module tests the complete flow from pattern detection
to trade execution and notifications.
"""

import unittest
import asyncio
import os
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock

from notifications.telegram_bot import TelegramBot
from notifications.telegram_notifications import TelegramNotifier
from trading.hummingbot_client import HummingbotClient
from analysis.volume_analyzer import VolumeAnalyzer
from analysis.profit_loss import ProfitLossTracker
from data_parsing.safety_analyzer import SafetyAnalyzer
from data_parsing.rugcheck_client import RugcheckClient
from config.settings import load_config, validate_config

class TestDeepSeekerE2E(unittest.TestCase):
    """End-to-end test cases for DeepSeeker Bot."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        # Load configuration
        cls.config = load_config()
        
        # Create mock objects
        cls.mock_telegram = Mock()
        cls.mock_telegram.send_alert = AsyncMock()
        
        # Mock telegram notifier
        cls.telegram_notifier = Mock()
        cls.telegram_notifier.send_message = AsyncMock()
        cls.telegram_notifier.send_error = AsyncMock()
        cls.telegram_notifier.send_performance_report = AsyncMock()
        
        # Initialize components
        cls.volume_analyzer = VolumeAnalyzer()
        cls.profit_loss = ProfitLossTracker(
            telegram_notifier=cls.telegram_notifier
        )
        cls.safety_analyzer = SafetyAnalyzer(
            rugcheck_api_key=cls.config['exchanges']['binance']['api_key']
        )
        cls.hummingbot = HummingbotClient(
            config=cls.config,
            telegram_bot=cls.mock_telegram
        )

    async def test_pattern_detection_to_trade(self):
        """Test complete flow from pattern detection to trade execution."""
        # 1. Simulate volume spike pattern
        pattern_data = {
            'symbol': 'BTC-USDT',
            'price': Decimal('50000.00'),
            'volume_change': Decimal('250.0'),
            'price_change': Decimal('5.2'),
            'timestamp': datetime.now()
        }
        
        # 2. Analyze pattern
        is_pump = await self.volume_analyzer.detect_pump(
            price_change=pattern_data['price_change'],
            volume_change=pattern_data['volume_change'],
            timeframe_minutes=5
        )
        
        self.assertTrue(is_pump)
        
        # 3. Check token safety
        safety_result = await self.safety_analyzer.analyze_token(
            token_address='0x2170Ed0880ac9A755fd29B2688956BD959F933F8',  # Example BTC
            chain_id=1
        )
        
        self.assertTrue(safety_result.is_safe)
        self.assertGreater(safety_result.safety_score, 80)
        
        # 4. Execute trade
        await self.hummingbot.setup()
        
        # Mock successful trade
        trade_details = {
            'type': 'BUY',
            'symbol': pattern_data['symbol'],
            'amount': Decimal('0.1'),
            'price': pattern_data['price'],
            'timestamp': datetime.now()
        }
        
        # Record trade
        await self.profit_loss.record_trade(
            symbol=trade_details['symbol'],
            trade_type=trade_details['type'],
            amount=trade_details['amount'],
            price=trade_details['price']
        )
        
        # Verify trade notification
        self.telegram_notifier.send_message.assert_called()
        call_args = self.telegram_notifier.send_message.call_args[0]
        self.assertIn('BUY Order Filled', call_args[0])
        self.assertIn(pattern_data['symbol'], call_args[0])

    async def test_rugpull_detection(self):
        """Test rugpull detection and alert system."""
        # 1. Simulate rugpull pattern
        rugpull_data = {
            'token_address': '0x123...abc',
            'liquidity_change': Decimal('-75.0'),
            'price_change': Decimal('-60.0'),
            'timestamp': datetime.now()
        }
        
        # 2. Analyze safety
        safety_result = await self.safety_analyzer.analyze_token(
            token_address=rugpull_data['token_address'],
            chain_id=1
        )
        
        self.assertFalse(safety_result.is_safe)
        self.assertLess(safety_result.safety_score, 30)
        
        # 3. Verify alert
        self.telegram_notifier.send_error.assert_called()
        call_args = self.telegram_notifier.send_error.call_args[0]
        self.assertIn('Risk Alert', call_args[0])
        self.assertIn('High', call_args[0])

    async def test_performance_reporting(self):
        """Test performance tracking and reporting."""
        # 1. Record sample trades
        trades = [
            {
                'symbol': 'BTC-USDT',
                'type': 'BUY',
                'amount': Decimal('0.1'),
                'price': Decimal('50000.00')
            },
            {
                'symbol': 'BTC-USDT',
                'type': 'SELL',
                'amount': Decimal('0.1'),
                'price': Decimal('52000.00')
            }
        ]
        
        for trade in trades:
            await self.profit_loss.record_trade(
                symbol=trade['symbol'],
                trade_type=trade['type'],
                amount=trade['amount'],
                price=trade['price']
            )
        
        # 2. Generate performance report
        report = await self.profit_loss.get_performance_summary()
        
        # 3. Verify report
        self.assertEqual(report['total_trades'], 2)
        self.assertEqual(report['winning_trades'], 1)
        self.assertEqual(report['win_rate'], 100.0)
        self.assertEqual(
            report['total_realized_pnl'],
            Decimal('200.00')  # (52000 - 50000) * 0.1
        )

    async def test_error_handling(self):
        """Test error handling and notifications."""
        # 1. Simulate API error
        with patch('aiohttp.ClientSession.get', side_effect=Exception('API Error')):
            with self.assertRaises(Exception):
                await self.safety_analyzer.analyze_token(
                    token_address='0x123...abc',
                    chain_id=1
                )
        
        # 2. Verify error notification
        self.telegram_notifier.send_error.assert_called()
        call_args = self.telegram_notifier.send_error.call_args[0]
        self.assertIn('Error', call_args[0])
        self.assertIn('API Error', call_args[0])

    async def test_configuration_validation(self):
        """Test configuration validation."""
        # 1. Test valid configuration
        self.assertTrue(validate_config(self.config))
        
        # 2. Test invalid configuration
        invalid_config = self.config.copy()
        invalid_config['trading']['min_order_size'] = -1
        
        with self.assertRaises(ValueError):
            validate_config(invalid_config)

def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestDeepSeekerE2E)
    runner = unittest.TextTestRunner()
    runner.run(suite)

if __name__ == '__main__':
    asyncio.run(run_tests())
