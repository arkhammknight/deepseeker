"""
Test module for the combined safety analyzer.
"""

import asyncio
import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from .safety_analyzer import SafetyAnalyzer
from .rugcheck_client import RugcheckResult

class TestSafetyAnalyzer(unittest.TestCase):
    """Test cases for safety analyzer functionality."""

    def setUp(self):
        """Set up test cases."""
        self.analyzer = SafetyAnalyzer()

    def create_mock_dex_data(self, is_risky: bool = False) -> dict:
        """Create mock DexScreener data."""
        if is_risky:
            return {
                'liquidity': {'usd': 5000},  # Low liquidity
                'volume': {'h24': 500},      # Low volume
                'priceImpact': {'buy1000': 0.08}  # High price impact
            }
        else:
            return {
                'liquidity': {'usd': 100000},
                'volume': {'h24': 50000},
                'priceImpact': {'buy1000': 0.02}
            }

    def create_mock_rugcheck_result(self, risk_level: str) -> RugcheckResult:
        """Create mock Rugcheck result."""
        risk_factors = []
        if risk_level in ['HIGH', 'CRITICAL']:
            risk_factors = [
                'Contract not verified',
                'Potential honeypot detected',
                'Owner is a contract'
            ]
        elif risk_level == 'MEDIUM':
            risk_factors = ['Owner is a contract']

        return RugcheckResult(
            token_address='0x123...',
            is_safe=risk_level in ['SAFE', 'MEDIUM'],
            risk_level=risk_level,
            risk_factors=risk_factors,
            contract_verified=risk_level == 'SAFE',
            holder_analysis={'top_holder_percentage': 15},
            timestamp=datetime.now(),
            raw_data={}
        )

    @patch('data_parsing.safety_analyzer.DexScreenerClient')
    @patch('data_parsing.safety_analyzer.RugcheckClient')
    async def test_safe_token_analysis(self, mock_rugcheck, mock_dexscreener):
        """Test analysis of a safe token."""
        # Setup mocks
        mock_dexscreener.return_value.get_token.return_value = \
            self.create_mock_dex_data(is_risky=False)
        mock_rugcheck.return_value.check_token.return_value = \
            self.create_mock_rugcheck_result('SAFE')
        mock_rugcheck.return_value.get_bundled_tokens.return_value = []

        # Perform analysis
        analysis = await self.analyzer.analyze_token('0x123...')

        self.assertTrue(analysis.is_safe)
        self.assertEqual(analysis.risk_level, 'SAFE')
        self.assertEqual(len(analysis.risk_factors), 0)
        self.assertIn('SAFE', analysis.recommendation)

    @patch('data_parsing.safety_analyzer.DexScreenerClient')
    @patch('data_parsing.safety_analyzer.RugcheckClient')
    async def test_high_risk_token_analysis(self, mock_rugcheck, mock_dexscreener):
        """Test analysis of a high-risk token."""
        # Setup mocks
        mock_dexscreener.return_value.get_token.return_value = \
            self.create_mock_dex_data(is_risky=True)
        mock_rugcheck.return_value.check_token.return_value = \
            self.create_mock_rugcheck_result('HIGH')
        mock_rugcheck.return_value.get_bundled_tokens.return_value = []

        # Perform analysis
        analysis = await self.analyzer.analyze_token('0x456...')

        self.assertFalse(analysis.is_safe)
        self.assertEqual(analysis.risk_level, 'HIGH')
        self.assertGreater(len(analysis.risk_factors), 0)
        self.assertIn('HIGH RISK', analysis.recommendation)

    @patch('data_parsing.safety_analyzer.DexScreenerClient')
    @patch('data_parsing.safety_analyzer.RugcheckClient')
    async def test_bundled_token_analysis(self, mock_rugcheck, mock_dexscreener):
        """Test analysis of a bundled token."""
        # Setup mocks
        mock_rugcheck.return_value.get_bundled_tokens.return_value = \
            ['0x789...', '0xabc...']

        # First analyze a token to populate bundled tokens set
        await self.analyzer.analyze_token('0x123...')

        # Then analyze a bundled token
        analysis = await self.analyzer.analyze_token('0x789...')

        self.assertFalse(analysis.is_safe)
        self.assertEqual(analysis.risk_level, 'HIGH')
        self.assertTrue(any('bundle' in factor.lower() 
                          for factor in analysis.risk_factors))
        self.assertIn('bundle', analysis.recommendation.lower())

    @patch('data_parsing.safety_analyzer.DexScreenerClient')
    @patch('data_parsing.safety_analyzer.RugcheckClient')
    async def test_error_handling(self, mock_rugcheck, mock_dexscreener):
        """Test error handling in analysis."""
        # Setup mocks to raise exceptions
        mock_dexscreener.return_value.get_token.side_effect = Exception("API Error")
        mock_rugcheck.return_value.check_token.side_effect = Exception("API Error")

        # Perform analysis
        analysis = await self.analyzer.analyze_token('0xdef...')

        self.assertFalse(analysis.is_safe)
        self.assertEqual(analysis.risk_level, 'UNKNOWN')
        self.assertTrue(any('error' in factor.lower() 
                          for factor in analysis.risk_factors))
        self.assertIn('Unable to complete', analysis.recommendation)

    def test_cache_functionality(self):
        """Test analysis caching."""
        token_address = '0x123...'
        mock_analysis = self.analyzer._create_error_analysis(
            token_address, "Test analysis"
        )
        
        # Add to cache
        self.analyzer.analysis_cache[token_address] = mock_analysis
        
        # Retrieve from cache
        cached = self.analyzer.get_cached_analysis(token_address)
        self.assertEqual(cached, mock_analysis)
        
        # Clear cache
        self.analyzer.clear_cache()
        self.assertIsNone(self.analyzer.get_cached_analysis(token_address))

if __name__ == '__main__':
    unittest.main()
