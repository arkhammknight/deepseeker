"""
Test module for filter and blacklist functionality.
"""

import asyncio
import unittest
from datetime import datetime, timedelta
from .filter_manager import FilterManager
from .filter_config import ConfigManager

class TestFilters(unittest.TestCase):
    """Test cases for filter functionality."""

    def setUp(self):
        """Set up test cases."""
        self.filter_manager = FilterManager('config/test_filter_settings.json')

    async def test_basic_filters(self):
        """Test basic filter criteria."""
        # Test token that should pass all filters
        good_token = {
            'address': '0x123...',
            'market_cap': 1000000,  # $1M
            'liquidity': 100000,    # $100K
            'holders': 1000,
            'creation_time': datetime.now() - timedelta(days=30),
            'max_holder_percentage': 0.05,  # 5%
            'daily_volume': 50000,  # $50K
            'price_impact': 0.02,   # 2%
            'developer': '0xabc...',
            'contract_code': 'standard_code'
        }
        
        passed, reasons = await self.filter_manager.apply_filters(good_token)
        self.assertTrue(passed)
        self.assertEqual(len(reasons), 0)

        # Test token that should fail multiple filters
        bad_token = {
            'address': '0x456...',
            'market_cap': 10000,    # $10K
            'liquidity': 5000,      # $5K
            'holders': 20,
            'creation_time': datetime.now() - timedelta(hours=12),
            'max_holder_percentage': 0.25,  # 25%
            'daily_volume': 1000,   # $1K
            'price_impact': 0.15,   # 15%
            'developer': '0xdef...',
            'contract_code': 'suspicious_code'
        }
        
        passed, reasons = await self.filter_manager.apply_filters(bad_token)
        self.assertFalse(passed)
        self.assertGreater(len(reasons), 0)

    def test_blacklist_functionality(self):
        """Test blacklist functionality."""
        # Add token to blacklist
        self.filter_manager.add_to_blacklist(
            '0x789...', 
            'tokens', 
            'Known rug pull'
        )

        # Add developer to blacklist
        self.filter_manager.add_to_blacklist(
            '0xdef...', 
            'developers', 
            'Multiple scam projects'
        )

        # Test blacklisted token
        blacklisted_token = {
            'address': '0x789...',
            'market_cap': 1000000,
            'liquidity': 100000,
            'holders': 1000,
            'developer': '0xabc...'
        }
        
        async def check_blacklisted():
            passed, reasons = await self.filter_manager.apply_filters(blacklisted_token)
            self.assertFalse(passed)
            self.assertTrue(any('blacklisted' in reason.lower() for reason in reasons))

        asyncio.run(check_blacklisted())

        # Test token with blacklisted developer
        token_with_bad_dev = {
            'address': '0xaaa...',
            'market_cap': 1000000,
            'liquidity': 100000,
            'holders': 1000,
            'developer': '0xdef...'
        }
        
        async def check_bad_dev():
            passed, reasons = await self.filter_manager.apply_filters(token_with_bad_dev)
            self.assertFalse(passed)
            self.assertTrue(any('developer blacklisted' in reason.lower() for reason in reasons))

        asyncio.run(check_bad_dev())

    def test_filter_settings_update(self):
        """Test updating filter settings."""
        new_settings = {
            'min_market_cap': 200000,
            'min_liquidity': 20000,
            'min_holders': 100
        }
        
        self.filter_manager.update_filter_settings(new_settings)
        
        # Test token that would pass old settings but fail new ones
        token = {
            'address': '0xbbb...',
            'market_cap': 150000,   # Fails new minimum
            'liquidity': 15000,     # Fails new minimum
            'holders': 80,          # Fails new minimum
            'creation_time': datetime.now() - timedelta(days=30),
            'max_holder_percentage': 0.05,
            'daily_volume': 50000,
            'price_impact': 0.02
        }
        
        async def check_updated_settings():
            passed, reasons = await self.filter_manager.apply_filters(token)
            self.assertFalse(passed)
            self.assertGreater(len(reasons), 0)

        asyncio.run(check_updated_settings())

if __name__ == '__main__':
    unittest.main()
