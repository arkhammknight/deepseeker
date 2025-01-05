"""
Base API client implementations for interacting with blockchain and token data sources.
"""

class BaseAPIClient:
    def __init__(self):
        self.base_url = None
        self.api_key = None

    def set_credentials(self, api_key):
        """Set API credentials."""
        self.api_key = api_key

    async def get_token_data(self, token_address):
        """Fetch token data from API."""
        raise NotImplementedError

    async def get_price_history(self, token_address, timeframe):
        """Fetch historical price data."""
        raise NotImplementedError

    async def get_liquidity_info(self, token_address):
        """Fetch liquidity information."""
        raise NotImplementedError
