"""
Client for interacting with Honeypot.is API.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
import logging

logger = logging.getLogger(__name__)

@dataclass
class HoneypotResult:
    """Results from Honeypot.is analysis."""
    token_address: str
    is_honeypot: bool
    buy_tax: float
    sell_tax: float
    max_tx_amount: Optional[float]
    holder_analysis: Dict
    simulation_success: bool
    simulation_error: Optional[str]
    timestamp: datetime
    raw_data: Dict

class HoneypotClient:
    """Client for interacting with Honeypot.is API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Honeypot.is API client.

        Args:
            api_key: Optional API key for extended functionality
        """
        self.base_url = "https://api.honeypot.is/v2"
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

    async def check_token(self, token_address: str) -> HoneypotResult:
        """
        Check if a token is a honeypot.

        Args:
            token_address: Token address to check

        Returns:
            HoneypotResult: Analysis results
        """
        if self._is_cache_valid(token_address):
            return self.cache[token_address]

        try:
            url = f"{self.base_url}/tokens/{token_address}"
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Honeypot.is API error: {response.status}")
                    raise ValueError(f"Honeypot.is API error: {response.status}")
                
                data = await response.json()
                result = self._parse_honeypot_response(token_address, data)
                self.cache[token_address] = result
                return result

        except Exception as e:
            logger.error(f"Error checking token on Honeypot.is: {str(e)}")
            raise

    def _parse_honeypot_response(
        self, token_address: str, data: Dict
    ) -> HoneypotResult:
        """
        Parse Honeypot.is API response.

        Args:
            token_address: Token address
            data: API response data

        Returns:
            HoneypotResult: Parsed results
        """
        simulation = data.get("simulation", {})
        return HoneypotResult(
            token_address=token_address,
            is_honeypot=data.get("is_honeypot", True),
            buy_tax=data.get("buy_tax", 0.0),
            sell_tax=data.get("sell_tax", 0.0),
            max_tx_amount=data.get("max_tx_amount"),
            holder_analysis=data.get("holder_analysis", {}),
            simulation_success=simulation.get("success", False),
            simulation_error=simulation.get("error"),
            timestamp=datetime.now(),
            raw_data=data
        )
