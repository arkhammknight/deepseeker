"""
Rugcheck.xyz API client for token safety analysis.

This module implements a client for the Rugcheck.xyz API to perform
contract safety checks and identify suspicious tokens.
"""

import logging
import aiohttp
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class RugcheckResult:
    """Results from Rugcheck.xyz analysis."""
    token_address: str
    is_safe: bool
    risk_level: str  # 'SAFE', 'MEDIUM', 'HIGH', 'CRITICAL'
    risk_factors: List[str]
    contract_verified: bool
    holder_analysis: Dict
    timestamp: datetime
    raw_data: Dict

class RugcheckClient:
    """Client for interacting with Rugcheck.xyz API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Rugcheck.xyz API client.

        Args:
            api_key: Optional API key for extended functionality
        """
        self.base_url = "https://api.rugcheck.xyz/v1"
        self.api_key = api_key
        self.session = None
        self.cache = {}
        self.cache_duration = timedelta(minutes=30)

    async def __aenter__(self):
        """Create aiohttp session when entering context."""
        self.session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session when exiting context."""
        if self.session:
            await self.session.close()

    def _is_cache_valid(self, token_address: str) -> bool:
        """
        Check if cached data is still valid.

        Args:
            token_address: Token address to check

        Returns:
            bool: True if cache is valid, False otherwise
        """
        if token_address not in self.cache:
            return False
        
        cache_time = self.cache[token_address].timestamp
        return datetime.now() - cache_time < self.cache_duration

    async def check_token(self, token_address: str) -> RugcheckResult:
        """
        Check a token's safety using Rugcheck.xyz.

        Args:
            token_address: Token address to check

        Returns:
            RugcheckResult: Analysis results
        """
        if self._is_cache_valid(token_address):
            return self.cache[token_address]

        try:
            if not self.session:
                self.session = aiohttp.ClientSession(
                    headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                )

            async with self.session.get(
                f"{self.base_url}/check/{token_address}"
            ) as response:
                response.raise_for_status()
                data = await response.json()

                result = self._parse_rugcheck_response(token_address, data)
                self.cache[token_address] = result
                return result

        except aiohttp.ClientError as e:
            logger.error(f"Rugcheck API request failed: {str(e)}")
            return self._create_error_result(token_address, f"API request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Rugcheck API response: {str(e)}")
            return self._create_error_result(token_address, "Invalid API response")
        except Exception as e:
            logger.error(f"Unexpected error in Rugcheck check: {str(e)}")
            return self._create_error_result(token_address, f"Unexpected error: {str(e)}")

    def _parse_rugcheck_response(self, token_address: str, data: Dict) -> RugcheckResult:
        """
        Parse Rugcheck.xyz API response.

        Args:
            token_address: Token address
            data: API response data

        Returns:
            RugcheckResult: Parsed results
        """
        risk_factors = []
        
        # Extract contract verification status
        contract_verified = data.get('contract', {}).get('verified', False)
        if not contract_verified:
            risk_factors.append("Contract not verified")

        # Check for honeypot characteristics
        if data.get('honeypot', {}).get('is_honeypot', False):
            risk_factors.append("Potential honeypot detected")

        # Analyze ownership
        ownership = data.get('ownership', {})
        if ownership.get('owner_is_contract', False):
            risk_factors.append("Owner is a contract")
        if ownership.get('renounced', False):
            risk_factors.append("Ownership renounced")

        # Check holder distribution
        holders = data.get('holders', {})
        top_holder_pct = holders.get('top_holder_percentage', 0)
        if top_holder_pct > 20:
            risk_factors.append(f"Top holder owns {top_holder_pct}% of supply")

        # Determine risk level
        risk_level = self._calculate_risk_level(risk_factors, data)

        return RugcheckResult(
            token_address=token_address,
            is_safe=risk_level in ['SAFE', 'MEDIUM'],
            risk_level=risk_level,
            risk_factors=risk_factors,
            contract_verified=contract_verified,
            holder_analysis=holders,
            timestamp=datetime.now(),
            raw_data=data
        )

    def _calculate_risk_level(self, risk_factors: List[str], data: Dict) -> str:
        """
        Calculate overall risk level based on factors.

        Args:
            risk_factors: List of identified risk factors
            data: Raw API response data

        Returns:
            str: Risk level classification
        """
        if data.get('honeypot', {}).get('is_honeypot', False):
            return 'CRITICAL'
        
        if len(risk_factors) >= 3:
            return 'HIGH'
        elif len(risk_factors) >= 2:
            return 'MEDIUM'
        elif len(risk_factors) >= 1:
            return 'MEDIUM'
        else:
            return 'SAFE'

    def _create_error_result(self, token_address: str, error_message: str) -> RugcheckResult:
        """
        Create error result when API call fails.

        Args:
            token_address: Token address
            error_message: Error message

        Returns:
            RugcheckResult: Error result
        """
        return RugcheckResult(
            token_address=token_address,
            is_safe=False,
            risk_level='UNKNOWN',
            risk_factors=[f"Error: {error_message}"],
            contract_verified=False,
            holder_analysis={},
            timestamp=datetime.now(),
            raw_data={}
        )

    async def get_bundled_tokens(self, token_address: str) -> List[str]:
        """
        Get list of tokens bundled with the given token.

        Args:
            token_address: Token address to check

        Returns:
            List[str]: List of bundled token addresses
        """
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(
                    headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                )

            async with self.session.get(
                f"{self.base_url}/bundles/{token_address}"
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get('bundled_tokens', [])

        except Exception as e:
            logger.error(f"Error getting bundled tokens: {str(e)}")
            return []

    def clear_cache(self) -> None:
        """Clear the API response cache."""
        self.cache.clear()
