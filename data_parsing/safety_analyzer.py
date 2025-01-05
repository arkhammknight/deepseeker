"""
Combined safety analyzer using data from multiple sources.

This module combines data from DexScreener, Rugcheck.xyz, TokenSniffer, Honeypot.is, and a blacklist manager to provide
comprehensive token safety analysis.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from .dexscreener_client import DexScreenerClient
from .rugcheck_client import RugcheckClient, RugcheckResult
from .tokensniffer_client import TokenSnifferClient, TokenSnifferResult
from .honeypot_client import HoneypotClient, HoneypotResult
from .blacklist_manager import BlacklistManager
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class SafetyAnalysis:
    """Combined safety analysis results."""
    token_address: str
    is_safe: bool
    risk_level: str
    risk_factors: List[str]
    dex_data: Dict
    rugcheck_data: Optional[RugcheckResult]
    tokensniffer_data: Optional[TokenSnifferResult]
    honeypot_data: Optional[HoneypotResult]
    blacklist_info: Optional[str]
    timestamp: datetime
    recommendation: str

class SafetyAnalyzer:
    """Analyzer combining multiple data sources for comprehensive safety analysis."""

    def __init__(
        self,
        rugcheck_api_key: Optional[str] = None,
        tokensniffer_api_key: Optional[str] = None,
        honeypot_api_key: Optional[str] = None
    ):
        """
        Initialize the safety analyzer.

        Args:
            rugcheck_api_key: Optional API key for Rugcheck.xyz
            tokensniffer_api_key: Optional API key for TokenSniffer
            honeypot_api_key: Optional API key for Honeypot.is
        """
        self.dex_client = DexScreenerClient()
        self.rugcheck_client = RugcheckClient(rugcheck_api_key)
        self.tokensniffer_client = TokenSnifferClient(tokensniffer_api_key)
        self.honeypot_client = HoneypotClient(honeypot_api_key)
        self.blacklist_manager = BlacklistManager()
        self.analysis_cache = {}

    async def __aenter__(self):
        """Set up API clients."""
        self.dex_client = await self.dex_client.__aenter__()
        self.rugcheck_client = await self.rugcheck_client.__aenter__()
        self.tokensniffer_client = await self.tokensniffer_client.__aenter__()
        self.honeypot_client = await self.honeypot_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up API clients."""
        await self.dex_client.__aexit__(exc_type, exc_val, exc_tb)
        await self.rugcheck_client.__aexit__(exc_type, exc_val, exc_tb)
        await self.tokensniffer_client.__aexit__(exc_type, exc_val, exc_tb)
        await self.honeypot_client.__aexit__(exc_type, exc_val, exc_tb)

    async def analyze_token(self, token_address: str) -> SafetyAnalysis:
        """
        Perform comprehensive token safety analysis.

        Args:
            token_address: Token address to analyze

        Returns:
            SafetyAnalysis: Combined analysis results
        """
        # Check blacklist first
        if self.blacklist_manager.is_blacklisted(token_address):
            reason = self.blacklist_manager.get_blacklist_reason(token_address)
            return SafetyAnalysis(
                token_address=token_address,
                is_safe=False,
                risk_level="CRITICAL",
                risk_factors=["Token is blacklisted"],
                dex_data={},
                rugcheck_data=None,
                tokensniffer_data=None,
                honeypot_data=None,
                blacklist_info=reason,
                timestamp=datetime.now(),
                recommendation="DO NOT TRADE - Token is blacklisted"
            )

        try:
            # Gather data from all sources
            dex_data = await self.dex_client.get_token_data(token_address)
            
            # Run all checks in parallel
            rugcheck_result, tokensniffer_result, honeypot_result = await asyncio.gather(
                self.rugcheck_client.check_token(token_address),
                self.tokensniffer_client.check_token(token_address),
                self.honeypot_client.check_token(token_address)
            )

            # Combine risk factors and determine overall risk level
            risk_factors = []
            risk_scores = []

            # Add Rugcheck.xyz risks
            if rugcheck_result:
                risk_factors.extend(rugcheck_result.risk_factors)
                if not rugcheck_result.is_safe:
                    risk_scores.append(3)  # High risk

            # Add TokenSniffer risks
            if tokensniffer_result:
                if tokensniffer_result.is_honeypot:
                    risk_factors.append("Potential honeypot detected by TokenSniffer")
                    risk_scores.append(3)
                if tokensniffer_result.has_mint_function:
                    risk_factors.append("Contract has mint function")
                    risk_scores.append(2)
                if tokensniffer_result.owner_balance_percent > 50:
                    risk_factors.append(f"Owner holds {tokensniffer_result.owner_balance_percent}% of supply")
                    risk_scores.append(2)
                
                # Convert TokenSniffer score (0-100) to risk score (0-3)
                trust_score_risk = 3 - (tokensniffer_result.trust_score / 33.33)
                risk_scores.append(max(0, min(3, trust_score_risk)))

            # Add Honeypot.is risks
            if honeypot_result:
                if honeypot_result.is_honeypot:
                    risk_factors.append("Potential honeypot detected by Honeypot.is")
                    risk_scores.append(3)
                if honeypot_result.buy_tax > 10:
                    risk_factors.append(f"High buy tax: {honeypot_result.buy_tax}%")
                    risk_scores.append(2)
                if honeypot_result.sell_tax > 10:
                    risk_factors.append(f"High sell tax: {honeypot_result.sell_tax}%")
                    risk_scores.append(2)

            # Calculate overall risk level
            avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 3
            risk_level = "SAFE" if avg_risk < 1 else \
                        "MEDIUM" if avg_risk < 2 else \
                        "HIGH" if avg_risk < 2.5 else \
                        "CRITICAL"

            # Generate detailed recommendation
            recommendation = self._generate_recommendation(
                risk_level,
                risk_factors,
                rugcheck_result,
                tokensniffer_result,
                honeypot_result,
                dex_data
            )

            return SafetyAnalysis(
                token_address=token_address,
                is_safe=risk_level in ["SAFE", "MEDIUM"],
                risk_level=risk_level,
                risk_factors=risk_factors,
                dex_data=dex_data,
                rugcheck_data=rugcheck_result,
                tokensniffer_data=tokensniffer_result,
                honeypot_data=honeypot_result,
                blacklist_info=None,
                timestamp=datetime.now(),
                recommendation=recommendation
            )

        except Exception as e:
            logger.error(f"Error analyzing token {token_address}: {str(e)}")
            raise

    def _generate_recommendation(
        self,
        risk_level: str,
        risk_factors: List[str],
        rugcheck_result: Optional[RugcheckResult],
        tokensniffer_result: Optional[TokenSnifferResult],
        honeypot_result: Optional[HoneypotResult],
        dex_data: Dict
    ) -> str:
        """
        Generate recommendation based on analysis.

        Args:
            risk_level: Overall risk level
            risk_factors: List of risk factors
            rugcheck_result: Results from Rugcheck
            tokensniffer_result: Results from TokenSniffer
            honeypot_result: Results from Honeypot.is
            dex_data: Data from DexScreener

        Returns:
            str: Detailed recommendation
        """
        if risk_level == "CRITICAL":
            return "DO NOT TRADE - Multiple critical risk factors detected"

        if risk_level == "HIGH":
            return "EXTREME CAUTION - High risk token with multiple warning signs"

        recommendation_parts = []

        if risk_level == "MEDIUM":
            recommendation_parts.append("CAUTION - Trade with limited exposure")
        else:
            recommendation_parts.append("MODERATE RISK - Standard trading precautions apply")

        # Add specific recommendations based on analysis
        if honeypot_result and (honeypot_result.buy_tax > 0 or honeypot_result.sell_tax > 0):
            recommendation_parts.append(
                f"Note: Buy tax {honeypot_result.buy_tax}%, Sell tax {honeypot_result.sell_tax}%"
            )

        if tokensniffer_result and tokensniffer_result.has_anti_whale:
            recommendation_parts.append("Anti-whale measures detected - Check max transaction limits")

        if risk_factors:
            recommendation_parts.append("Risk factors to consider:")
            recommendation_parts.extend(f"- {factor}" for factor in risk_factors)

        return "\n".join(recommendation_parts)

    def get_cached_analysis(self, token_address: str) -> Optional[SafetyAnalysis]:
        """
        Get cached analysis for a token.

        Args:
            token_address: Token address to check

        Returns:
            Optional[SafetyAnalysis]: Cached analysis if available
        """
        return self.analysis_cache.get(token_address)

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.analysis_cache.clear()
        self.dex_client.clear_cache()
        self.rugcheck_client.clear_cache()
        self.tokensniffer_client.clear_cache()
        self.honeypot_client.clear_cache()
