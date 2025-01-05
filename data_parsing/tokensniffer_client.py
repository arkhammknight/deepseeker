"""
Client for interacting with TokenSniffer API.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
import logging

logger = logging.getLogger(__name__)

@dataclass
class TokenSnifferResult:
    """Results from TokenSniffer analysis."""
    token_address: str
    trust_score: float  # 0-100
    is_honeypot: bool
    has_anti_whale: bool
    has_blacklist: bool
    has_mint_function: bool
    owner_balance_percent: float
    holder_analysis: Dict
    timestamp: datetime
    raw_data: Dict

class TokenSnifferClient:
    """Client for interacting with TokenSniffer API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the TokenSniffer API client.

        Args:
            api_key: API key for TokenSniffer
        """
        self.base_url = "https://api.tokensniffer.com/v2"
        self.api_key = api_key
        self.session = None
        self.cache = {}
        self.cache_duration = timedelta(minutes=30)

    async def __aenter__(self):
        """Create aiohttp session when entering context."""
        self.session = aiohttp.ClientSession(
            headers={"X-API-KEY": self.api_key} if self.api_key else {}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session when exiting context."""
        if self.session:
            await self.session.close()

    def _is_cache_valid(self, token_address: str) -> bool:
        """Check if cached data is still valid."""
        if token_address not in self.cache:
            return False
        cache_time = self.cache[token_address].timestamp
        return datetime.now() - cache_time < self.cache_duration

    async def check_token(self, token_address: str) -> TokenSnifferResult:
        """
        Check a token's safety using TokenSniffer.

        Args:
            token_address: Token address to check

        Returns:
            TokenSnifferResult: Analysis results
        """
        if self._is_cache_valid(token_address):
            return self.cache[token_address]

        try:
            url = f"{self.base_url}/tokens/{token_address}"
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"TokenSniffer API error: {response.status}")
                    raise ValueError(f"TokenSniffer API error: {response.status}")
                
                data = await response.json()
                result = self._parse_tokensniffer_response(token_address, data)
                self.cache[token_address] = result
                return result

        except Exception as e:
            logger.error(f"Error checking token on TokenSniffer: {str(e)}")
            raise

    def _parse_tokensniffer_response(
        self, token_address: str, data: Dict
    ) -> TokenSnifferResult:
        """
        Parse TokenSniffer API response.

        Args:
            token_address: Token address
            data: API response data

        Returns:
            TokenSnifferResult: Parsed results
        """
        return TokenSnifferResult(
            token_address=token_address,
            trust_score=data.get("trust_score", 0.0),
            is_honeypot=data.get("is_honeypot", True),
            has_anti_whale=data.get("has_anti_whale", False),
            has_blacklist=data.get("has_blacklist", False),
            has_mint_function=data.get("has_mint_function", False),
            owner_balance_percent=data.get("owner_balance_percent", 0.0),
            holder_analysis=data.get("holder_analysis", {}),
            timestamp=datetime.now(),
            raw_data=data
        )
