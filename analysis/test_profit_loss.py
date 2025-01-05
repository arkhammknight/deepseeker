"""
Test module for profit and loss tracking functionality.
"""

import unittest
from unittest.mock import Mock, patch
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
import json
import tempfile
import os
from .profit_loss import ProfitLossTracker, Transaction, TradePosition

class TestProfitLossTracker(unittest.TestCase):
    """Test cases for profit/loss tracking functionality."""

    def setUp(self):
        """Set up test cases."""
        self.mock_notifier = Mock()
        self.mock_notifier.send_message = AsyncMock()
        self.tracker = ProfitLossTracker(self.mock_notifier)

    async def test_record_buy_transaction(self):
        """Test recording a buy transaction."""
        transaction = await self.tracker.record_transaction(
            token_address='0x123',
            token_symbol='TEST',
            transaction_type='BUY',
            quantity=Decimal('100'),
            price_usd=Decimal('1.5'),
            gas_fee_usd=Decimal('10'),
            transaction_hash='0xabc'
        )

        self.assertEqual(len(self.tracker.transactions), 1)
        self.assertEqual(len(self.tracker.positions['0x123']), 1)
        self.assertEqual(self.tracker.positions['0x123'][0].status, 'OPEN')
        
        # Verify notification was sent
        self.mock_notifier.send_message.assert_called_once()
        call_args = self.mock_notifier.send_message.call_args[0][0]
        self.assertIn('New Position', call_args)
        self.assertIn('TEST', call_args)

    async def test_complete_trade_cycle(self):
        """Test a complete trade cycle (buy and sell)."""
        # Record buy transaction
        await self.tracker.record_transaction(
            token_address='0x123',
            token_symbol='TEST',
            transaction_type='BUY',
            quantity=Decimal('100'),
            price_usd=Decimal('1.5'),
            gas_fee_usd=Decimal('10'),
            transaction_hash='0xabc'
        )

        # Record sell transaction
        await self.tracker.record_transaction(
            token_address='0x123',
            token_symbol='TEST',
            transaction_type='SELL',
            quantity=Decimal('100'),
            price_usd=Decimal('2.0'),
            gas_fee_usd=Decimal('10'),
            transaction_hash='0xdef'
        )

        position = self.tracker.positions['0x123'][0]
        self.assertEqual(position.status, 'CLOSED')
        self.assertIsNotNone(position.realized_pnl)
        self.assertIsNotNone(position.roi_percentage)
        
        # Verify both notifications were sent
        self.assertEqual(self.mock_notifier.send_message.call_count, 2)
        last_call_args = self.mock_notifier.send_message.call_args[0][0]
        self.assertIn('Position Closed', last_call_args)
        self.assertIn('P&L', last_call_args)

    async def test_profitable_trade(self):
        """Test calculations for a profitable trade."""
        # Buy at $1.5
        await self.tracker.record_transaction(
            token_address='0x123',
            token_symbol='TEST',
            transaction_type='BUY',
            quantity=Decimal('100'),
            price_usd=Decimal('1.5'),
            gas_fee_usd=Decimal('10'),
            transaction_hash='0xabc'
        )

        # Sell at $2.0
        await self.tracker.record_transaction(
            token_address='0x123',
            token_symbol='TEST',
            transaction_type='SELL',
            quantity=Decimal('100'),
            price_usd=Decimal('2.0'),
            gas_fee_usd=Decimal('10'),
            transaction_hash='0xdef'
        )

        position = self.tracker.positions['0x123'][0]
        expected_pnl = (Decimal('100') * Decimal('2.0')) - \
                      (Decimal('100') * Decimal('1.5')) - \
                      Decimal('20')  # Total gas fees
        
        self.assertEqual(position.realized_pnl, expected_pnl)
        self.assertTrue(position.realized_pnl > 0)
        self.assertEqual(self.tracker.winning_trades, 1)

    async def test_losing_trade(self):
        """Test calculations for a losing trade."""
        # Buy at $2.0
        await self.tracker.record_transaction(
            token_address='0x123',
            token_symbol='TEST',
            transaction_type='BUY',
            quantity=Decimal('100'),
            price_usd=Decimal('2.0'),
            gas_fee_usd=Decimal('10'),
            transaction_hash='0xabc'
        )

        # Sell at $1.5
        await self.tracker.record_transaction(
            token_address='0x123',
            token_symbol='TEST',
            transaction_type='SELL',
            quantity=Decimal('100'),
            price_usd=Decimal('1.5'),
            gas_fee_usd=Decimal('10'),
            transaction_hash='0xdef'
        )

        position = self.tracker.positions['0x123'][0]
        self.assertTrue(position.realized_pnl < 0)
        self.assertEqual(self.tracker.winning_trades, 0)

    async def test_performance_summary(self):
        """Test performance summary calculations."""
        # Add a winning trade
        await self.tracker.record_transaction(
            token_address='0x123',
            token_symbol='TEST1',
            transaction_type='BUY',
            quantity=Decimal('100'),
            price_usd=Decimal('1.5'),
            gas_fee_usd=Decimal('10'),
            transaction_hash='0xabc1'
        )
        await self.tracker.record_transaction(
            token_address='0x123',
            token_symbol='TEST1',
            transaction_type='SELL',
            quantity=Decimal('100'),
            price_usd=Decimal('2.0'),
            gas_fee_usd=Decimal('10'),
            transaction_hash='0xdef1'
        )

        # Add a losing trade
        await self.tracker.record_transaction(
            token_address='0x456',
            token_symbol='TEST2',
            transaction_type='BUY',
            quantity=Decimal('100'),
            price_usd=Decimal('2.0'),
            gas_fee_usd=Decimal('10'),
            transaction_hash='0xabc2'
        )
        await self.tracker.record_transaction(
            token_address='0x456',
            token_symbol='TEST2',
            transaction_type='SELL',
            quantity=Decimal('100'),
            price_usd=Decimal('1.5'),
            gas_fee_usd=Decimal('10'),
            transaction_hash='0xdef2'
        )

        summary = await self.tracker.get_performance_summary()
        self.assertEqual(summary['total_trades'], 2)
        self.assertEqual(summary['winning_trades'], 1)
        self.assertEqual(summary['win_rate'], 50.0)

    def test_file_operations(self):
        """Test saving and loading trading history."""
        # Create some test data
        asyncio.run(self.test_complete_trade_cycle())
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            self.tracker.save_to_file(tmp.name)
            
            # Create new tracker and load data
            new_tracker = ProfitLossTracker(self.mock_notifier)
            new_tracker.load_from_file(tmp.name)
            
            # Verify data was loaded correctly
            self.assertEqual(
                len(new_tracker.transactions),
                len(self.tracker.transactions)
            )
            self.assertEqual(
                len(new_tracker.positions['0x123']),
                len(self.tracker.positions['0x123'])
            )
            
            # Compare position details
            old_pos = self.tracker.positions['0x123'][0]
            new_pos = new_tracker.positions['0x123'][0]
            self.assertEqual(old_pos.realized_pnl, new_pos.realized_pnl)
            self.assertEqual(old_pos.roi_percentage, new_pos.roi_percentage)
            
        # Clean up
        os.unlink(tmp.name)

class AsyncMock(Mock):
    """Mock class that works with async functions."""
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)

if __name__ == '__main__':
    unittest.main()
