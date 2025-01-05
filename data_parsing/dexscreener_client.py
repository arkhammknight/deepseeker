"""
DexScreener API client for retrieving real-time token data.

This module provides a client for interacting with the DexScreener API to fetch
token information, price charts, and transaction history.
"""

import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DexScreenerClient:
    """Client for interacting with the DexScreener API."""
    
    BASE_URL = "https://api.dexscreener.com/latest"
    
    def __init__(self, cache_duration: int = 300):
        """
        Initialize the DexScreener API client.
        
        Args:
            cache_duration (int): Duration in seconds to cache API responses. Defaults to 5 minutes.
        """
        self.session = None
        self.cache = {}
        self.cache_duration = cache_duration
        self.cache_timestamps = {}

    async def __aenter__(self):
        """Create aiohttp session when entering context."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session when exiting context."""
        if self.session:
            await self.session.close()

    def _is_cache_valid(self, cache_key: str) -> bool:
        """
        Check if cached data is still valid.
        
        Args:
            cache_key (str): Key to check in cache
            
        Returns:
            bool: True if cache is valid, False otherwise
        """
        if cache_key not in self.cache_timestamps:
            return False
        
        cache_time = self.cache_timestamps[cache_key]
        return (datetime.now() - cache_time).seconds < self.cache_duration

    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make an HTTP request to the DexScreener API.
        
        Args:
            endpoint (str): API endpoint to call
            params (Optional[Dict]): Query parameters for the request
            
        Returns:
            Dict: JSON response from the API
            
        Raises:
            aiohttp.ClientError: If the request fails
            json.JSONDecodeError: If the response cannot be parsed as JSON
        """
        if self.session is None:
            self.session = aiohttp.ClientSession()

        url = f"{self.BASE_URL}/{endpoint}"
        cache_key = f"{url}:{json.dumps(params or {})}"

        # Check cache first
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                
                # Cache the response
                self.cache[cache_key] = data
                self.cache_timestamps[cache_key] = datetime.now()
                
                return data
        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse API response: {str(e)}")
            raise

    async def get_token(self, token_address: str) -> Dict:
        """
        Get detailed information about a specific token.
        
        Args:
            token_address (str): Token contract address
            
        Returns:
            Dict: Token information including price, liquidity, and other metrics
        """
        try:
            response = await self._make_request(f"tokens/{token_address}")
            if not response.get('pairs'):
                logger.warning(f"No pairs found for token {token_address}")
                return {}
            return response
        except Exception as e:
            logger.error(f"Failed to get token data: {str(e)}")
            return {}

    async def get_pair(self, pair_address: str) -> Dict:
        """
        Get detailed information about a specific trading pair.
        
        Args:
            pair_address (str): Pair contract address
            
        Returns:
            Dict: Pair information including price, liquidity, and volume
        """
        try:
            response = await self._make_request(f"pairs/{pair_address}")
            if not response.get('pair'):
                logger.warning(f"No data found for pair {pair_address}")
                return {}
            return response
        except Exception as e:
            logger.error(f"Failed to get pair data: {str(e)}")
            return {}

    async def search_pairs(self, query: str) -> List[Dict]:
        """
        Search for trading pairs by token name or address.
        
        Args:
            query (str): Search query (token name or address)
            
        Returns:
            List[Dict]: List of matching pairs
        """
        try:
            response = await self._make_request("search", {"q": query})
            return response.get('pairs', [])
        except Exception as e:
            logger.error(f"Failed to search pairs: {str(e)}")
            return []

    def clear_cache(self) -> None:
        """Clear the API response cache."""
        self.cache.clear()
        self.cache_timestamps.clear()

    async def get_recent_transactions(self, pair_address: str, limit: int = 100) -> List[Dict]:
        """
        Get recent transactions for a trading pair.
        
        Args:
            pair_address (str): Pair contract address
            limit (int): Maximum number of transactions to return
            
        Returns:
            List[Dict]: List of recent transactions
        """
        try:
            pair_data = await self.get_pair(pair_address)
            if not pair_data:
                return []
            
            # Note: DexScreener API currently doesn't provide detailed transaction history
            # This is a placeholder for when/if they add this endpoint
            return []
        except Exception as e:
            logger.error(f"Failed to get recent transactions: {str(e)}")
            return []

    async def get_price_history(self, pair_address: str) -> Dict:
        """
        Get historical price data for a trading pair.
        
        Args:
            pair_address (str): Pair contract address
            
        Returns:
            Dict: Historical price data including timestamps and prices
        """
        try:
            pair_data = await self.get_pair(pair_address)
            if not pair_data:
                return {}
            
            # Note: DexScreener API currently doesn't provide historical price data directly
            # This is a placeholder for when/if they add this endpoint
            return {
                'pair_address': pair_address,
                'current_price': pair_data.get('pair', {}).get('priceUsd'),
                'price_change_24h': pair_data.get('pair', {}).get('priceChange24h')
            }
        except Exception as e:
            logger.error(f"Failed to get price history: {str(e)}")
            return {}
