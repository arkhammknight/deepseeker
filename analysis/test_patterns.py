"""
Test module for pattern detection and analysis functionality.
"""

import asyncio
import unittest
from datetime import datetime, timedelta
from .pattern_detector import PatternDetector, PatternType
from .pattern_analyzer import PatternAnalyzer

class TestPatternDetection(unittest.TestCase):
    """Test cases for pattern detection algorithms."""

    def setUp(self):
        """Set up test cases."""
        self.detector = PatternDetector()
        self.analyzer = PatternAnalyzer()

    def test_liquidity_drop_detection(self):
        """Test liquidity drop detection."""
        # Test sudden liquidity drop
        current_liquidity = 50000
        historical_liquidity = [100000, 95000, 90000]
        alert = self.detector.detect_liquidity_drop(
            current_liquidity, historical_liquidity
        )
        self.assertIsNotNone(alert)
        self.assertEqual(alert.pattern_type, PatternType.RUG_PULL)
        self.assertEqual(alert.severity, 'HIGH')

        # Test normal liquidity fluctuation
        current_liquidity = 95000
        historical_liquidity = [100000, 98000, 96000]
        alert = self.detector.detect_liquidity_drop(
            current_liquidity, historical_liquidity
        )
        self.assertIsNone(alert)

    def test_pump_pattern_detection(self):
        """Test pump pattern detection."""
        # Test pump pattern
        price_data = [1.0, 1.1, 1.3, 1.8, 2.0]
        volume_data = [10000, 12000, 15000, 60000, 80000]
        timestamps = [
            datetime.now() - timedelta(hours=4),
            datetime.now() - timedelta(hours=3),
            datetime.now() - timedelta(hours=2),
            datetime.now() - timedelta(hours=1),
            datetime.now()
        ]
        alert = self.detector.detect_pump_pattern(
            price_data, volume_data, timestamps
        )
        self.assertIsNotNone(alert)
        self.assertEqual(alert.pattern_type, PatternType.PUMP_AND_DUMP)

        # Test normal price movement
        price_data = [1.0, 1.02, 1.03, 1.01, 1.02]
        volume_data = [10000, 11000, 10500, 10800, 11000]
        alert = self.detector.detect_pump_pattern(
            price_data, volume_data, timestamps
        )
        self.assertIsNone(alert)

    def test_unusual_volume_detection(self):
        """Test unusual volume detection."""
        # Test volume spike
        current_volume = 100000
        historical_volumes = [10000, 12000, 11000, 13000]
        alert = self.detector.detect_unusual_volume(
            current_volume, historical_volumes
        )
        self.assertIsNotNone(alert)
        self.assertEqual(alert.pattern_type, PatternType.UNUSUAL_VOLUME)

        # Test normal volume
        current_volume = 12000
        alert = self.detector.detect_unusual_volume(
            current_volume, historical_volumes
        )
        self.assertIsNone(alert)

class TestPatternAnalysis(unittest.TestCase):
    """Test cases for pattern analysis."""

    def setUp(self):
        """Set up test cases."""
        self.analyzer = PatternAnalyzer()

    async def test_token_analysis(self):
        """Test token analysis functionality."""
        # Test high risk scenario
        token_data = {
            'token_address': '0x123...',
            'liquidity_usd': 50000,
            'historical_liquidity': [100000, 90000, 80000],
            'price_history': [1.0, 1.1, 1.3, 1.8, 2.0],
            'volume_history': [10000, 12000, 15000, 60000, 80000],
            'timestamps': [
                datetime.now() - timedelta(hours=4),
                datetime.now() - timedelta(hours=3),
                datetime.now() - timedelta(hours=2),
                datetime.now() - timedelta(hours=1),
                datetime.now()
            ],
            'volume_24h': 80000,
            'historical_volumes': [10000, 12000, 11000, 13000]
        }

        result = await self.analyzer.analyze_token(token_data)
        self.assertGreaterEqual(result.risk_score, 0.8)
        self.assertGreater(len(result.patterns_detected), 0)

        # Test low risk scenario
        token_data = {
            'token_address': '0x456...',
            'liquidity_usd': 95000,
            'historical_liquidity': [100000, 98000, 96000],
            'price_history': [1.0, 1.02, 1.03, 1.01, 1.02],
            'volume_history': [10000, 11000, 10500, 10800, 11000],
            'timestamps': [
                datetime.now() - timedelta(hours=4),
                datetime.now() - timedelta(hours=3),
                datetime.now() - timedelta(hours=2),
                datetime.now() - timedelta(hours=1),
                datetime.now()
            ],
            'volume_24h': 11000,
            'historical_volumes': [10000, 10500, 11000, 10800]
        }

        result = await self.analyzer.analyze_token(token_data)
        self.assertLess(result.risk_score, 0.4)
        self.assertEqual(len(result.patterns_detected), 0)

if __name__ == '__main__':
    unittest.main()
