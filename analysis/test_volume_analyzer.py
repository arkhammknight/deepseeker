"""
Test module for volume analysis functionality.
"""

import asyncio
import unittest
from datetime import datetime, timedelta
import numpy as np
from .volume_analyzer import VolumeAnalyzer, OrderBookMetrics, VolumeAnalysis

class TestVolumeAnalyzer(unittest.TestCase):
    """Test cases for volume analysis functionality."""

    def setUp(self):
        """Set up test cases."""
        self.analyzer = VolumeAnalyzer()

    def generate_order_book(self, manipulated: bool = False) -> dict:
        """Generate sample order book data."""
        if manipulated:
            # Generate manipulated order book with walls and imbalance
            return {
                'bids': [
                    ['1.0', '100000'],  # Large wall
                    ['0.99', '100'],
                    ['0.98', '100'],
                ],
                'asks': [
                    ['1.01', '100'],
                    ['1.02', '100'],
                    ['1.03', '50000'],  # Large wall
                ]
            }
        else:
            # Generate healthy order book
            return {
                'bids': [
                    ['1.0', '1000'],
                    ['0.99', '1200'],
                    ['0.98', '800'],
                ],
                'asks': [
                    ['1.01', '900'],
                    ['1.02', '1100'],
                    ['1.03', '1000'],
                ]
            }

    def generate_trades(self, wash_trading: bool = False) -> list:
        """Generate sample trade data."""
        if wash_trading:
            # Generate trades with wash trading patterns
            return [
                {
                    'maker_address': 'trader1',
                    'taker_address': 'trader2',
                    'amount': '1000',
                    'side': 'buy',
                    'timestamp': datetime.now() - timedelta(minutes=5)
                },
                {
                    'maker_address': 'trader2',
                    'taker_address': 'trader1',
                    'amount': '1000',
                    'side': 'sell',
                    'timestamp': datetime.now() - timedelta(minutes=4)
                },
                {
                    'maker_address': 'trader1',
                    'taker_address': 'trader2',
                    'amount': '1000',
                    'side': 'buy',
                    'timestamp': datetime.now() - timedelta(minutes=3)
                }
            ]
        else:
            # Generate legitimate trading pattern
            return [
                {
                    'maker_address': 'trader1',
                    'taker_address': 'trader3',
                    'amount': '1000',
                    'side': 'buy',
                    'timestamp': datetime.now() - timedelta(minutes=5)
                },
                {
                    'maker_address': 'trader2',
                    'taker_address': 'trader4',
                    'amount': '800',
                    'side': 'sell',
                    'timestamp': datetime.now() - timedelta(minutes=4)
                },
                {
                    'maker_address': 'trader5',
                    'taker_address': 'trader6',
                    'amount': '1200',
                    'side': 'buy',
                    'timestamp': datetime.now() - timedelta(minutes=3)
                }
            ]

    async def test_order_book_analysis(self):
        """Test order book analysis."""
        # Test healthy order book
        healthy_book = self.generate_order_book(manipulated=False)
        metrics = await self.analyzer.analyze_order_book(healthy_book)
        
        self.assertLess(metrics.manipulation_score, 0.3)
        self.assertFalse(metrics.wall_detection)
        self.assertLess(metrics.concentration_score, 0.5)

        # Test manipulated order book
        manipulated_book = self.generate_order_book(manipulated=True)
        metrics = await self.analyzer.analyze_order_book(manipulated_book)
        
        self.assertGreater(metrics.manipulation_score, 0.7)
        self.assertTrue(metrics.wall_detection)
        self.assertGreater(metrics.concentration_score, 0.7)

    async def test_wash_trading_detection(self):
        """Test wash trading detection."""
        # Test legitimate trading
        normal_trades = self.generate_trades(wash_trading=False)
        wash_score = await self.analyzer._detect_wash_trading(normal_trades)
        self.assertLess(wash_score, 0.3)

        # Test wash trading
        wash_trades = self.generate_trades(wash_trading=True)
        wash_score = await self.analyzer._detect_wash_trading(wash_trades)
        self.assertGreater(wash_score, 0.7)

    async def test_volume_consistency(self):
        """Test volume consistency analysis."""
        # Test consistent volume
        consistent_volume = [1000, 1100, 900, 1050, 950]
        score = self.analyzer._analyze_volume_consistency(consistent_volume)
        self.assertGreater(score, 0.7)

        # Test inconsistent volume
        inconsistent_volume = [1000, 5000, 500, 10000, 100]
        score = self.analyzer._analyze_volume_consistency(inconsistent_volume)
        self.assertLess(score, 0.3)

    async def test_full_volume_analysis(self):
        """Test complete volume analysis."""
        # Test legitimate token
        legitimate_token = {
            'address': '0x123...',
            'order_book': self.generate_order_book(manipulated=False),
            'trades': self.generate_trades(wash_trading=False),
            'volume_history': [1000, 1100, 900, 1050, 950]
        }
        
        analysis = await self.analyzer.analyze_volume_patterns(legitimate_token)
        self.assertGreater(analysis.volume_legitimacy_score, 0.7)
        self.assertEqual(analysis.risk_level, 'LOW')
        self.assertEqual(len(analysis.suspicious_patterns), 0)

        # Test suspicious token
        suspicious_token = {
            'address': '0x456...',
            'order_book': self.generate_order_book(manipulated=True),
            'trades': self.generate_trades(wash_trading=True),
            'volume_history': [1000, 5000, 500, 10000, 100]
        }
        
        analysis = await self.analyzer.analyze_volume_patterns(suspicious_token)
        self.assertLess(analysis.volume_legitimacy_score, 0.3)
        self.assertEqual(analysis.risk_level, 'HIGH')
        self.assertGreater(len(analysis.suspicious_patterns), 0)

if __name__ == '__main__':
    unittest.main()
