"""
Filter manager module for applying filters and blacklists to tokens.

This module implements the filtering logic based on user-defined criteria
and maintains blacklists for tokens, developers, and contracts.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from .filter_config import ConfigManager, FilterConfig, BlacklistConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FilterManager:
    """Manager for applying filters and blacklists to tokens."""

    def __init__(self, config_path: str = 'config/filter_settings.json'):
        """
        Initialize the filter manager.

        Args:
            config_path: Path to the configuration file
        """
        self.config_manager = ConfigManager(config_path)
        self.filter_results_cache = {}

    async def apply_filters(self, token_data: Dict) -> Tuple[bool, List[str]]:
        """
        Apply all filters to a token.

        Args:
            token_data: Token data to filter

        Returns:
            Tuple[bool, List[str]]: (Passed filters?, List of failed filter reasons)
        """
        failed_reasons = []

        # Check blacklists first
        blacklist_result = self._check_blacklists(token_data)
        if blacklist_result:
            failed_reasons.append(f"Blacklisted: {blacklist_result}")
            return False, failed_reasons

        # Apply market cap filter
        market_cap = float(token_data.get('market_cap', 0))
        if market_cap < self.config_manager.filter_config.min_market_cap:
            failed_reasons.append(
                f"Market cap too low: ${market_cap:,.2f} < ${self.config_manager.filter_config.min_market_cap:,.2f}"
            )

        # Apply liquidity filter
        liquidity = float(token_data.get('liquidity', 0))
        if liquidity < self.config_manager.filter_config.min_liquidity:
            failed_reasons.append(
                f"Liquidity too low: ${liquidity:,.2f} < ${self.config_manager.filter_config.min_liquidity:,.2f}"
            )

        # Apply holders filter
        holders = int(token_data.get('holders', 0))
        if holders < self.config_manager.filter_config.min_holders:
            failed_reasons.append(
                f"Too few holders: {holders} < {self.config_manager.filter_config.min_holders}"
            )

        # Apply coin age filter
        creation_time = token_data.get('creation_time')
        if creation_time:
            age_days = (datetime.now() - creation_time).days
            if age_days < self.config_manager.filter_config.min_coin_age_days:
                failed_reasons.append(
                    f"Token too new: {age_days} days < {self.config_manager.filter_config.min_coin_age_days} days"
                )

        # Apply holder percentage filter
        max_holder_pct = float(token_data.get('max_holder_percentage', 0))
        if max_holder_pct > self.config_manager.filter_config.max_holder_percentage:
            failed_reasons.append(
                f"Holder concentration too high: {max_holder_pct*100:.1f}% > {self.config_manager.filter_config.max_holder_percentage*100:.1f}%"
            )

        # Apply volume filter
        daily_volume = float(token_data.get('daily_volume', 0))
        if daily_volume < self.config_manager.filter_config.min_daily_volume:
            failed_reasons.append(
                f"Volume too low: ${daily_volume:,.2f} < ${self.config_manager.filter_config.min_daily_volume:,.2f}"
            )

        # Apply price impact filter
        price_impact = float(token_data.get('price_impact', 0))
        if price_impact > self.config_manager.filter_config.max_price_impact:
            failed_reasons.append(
                f"Price impact too high: {price_impact*100:.1f}% > {self.config_manager.filter_config.max_price_impact*100:.1f}%"
            )

        # Cache the results
        self.filter_results_cache[token_data.get('address')] = {
            'timestamp': datetime.now(),
            'passed': len(failed_reasons) == 0,
            'reasons': failed_reasons
        }

        return len(failed_reasons) == 0, failed_reasons

    def _check_blacklists(self, token_data: Dict) -> Optional[str]:
        """
        Check if token is blacklisted.

        Args:
            token_data: Token data to check

        Returns:
            Optional[str]: Reason for blacklisting if found, None otherwise
        """
        # Check token address
        token_address = token_data.get('address')
        if token_address in self.config_manager.blacklist_config.blacklisted_tokens:
            return self.config_manager.get_blacklist_reason(token_address) or "Token blacklisted"

        # Check developer address
        developer = token_data.get('developer')
        if developer in self.config_manager.blacklist_config.blacklisted_developers:
            return self.config_manager.get_blacklist_reason(developer) or "Developer blacklisted"

        # Check contract patterns
        contract_code = token_data.get('contract_code', '')
        for pattern in self.config_manager.blacklist_config.blacklisted_contracts:
            if pattern in contract_code:
                return f"Blacklisted contract pattern found: {pattern}"

        return None

    def add_to_blacklist(self, 
                        address: str, 
                        blacklist_type: str, 
                        reason: str = None) -> None:
        """
        Add an address to a blacklist.

        Args:
            address: Address to blacklist
            blacklist_type: Type of blacklist ('tokens', 'developers', 'contracts')
            reason: Reason for blacklisting
        """
        self.config_manager.update_blacklist(address, blacklist_type, reason)
        logger.info(f"Added {address} to {blacklist_type} blacklist: {reason}")

    def remove_from_blacklist(self, 
                            address: str, 
                            blacklist_type: str) -> None:
        """
        Remove an address from a blacklist.

        Args:
            address: Address to remove
            blacklist_type: Type of blacklist ('tokens', 'developers', 'contracts')
        """
        self.config_manager.update_blacklist(address, blacklist_type, remove=True)
        logger.info(f"Removed {address} from {blacklist_type} blacklist")

    def update_filter_settings(self, new_settings: Dict) -> None:
        """
        Update filter settings.

        Args:
            new_settings: Dictionary of new filter settings
        """
        self.config_manager.update_filter_config(new_settings)
        logger.info("Updated filter settings")
        self.filter_results_cache.clear()  # Clear cache after settings update

    def get_filter_results(self, token_address: str) -> Optional[Dict]:
        """
        Get cached filter results for a token.

        Args:
            token_address: Token address to check

        Returns:
            Optional[Dict]: Cached filter results if available
        """
        result = self.filter_results_cache.get(token_address)
        if result and (datetime.now() - result['timestamp']).seconds < 3600:  # 1 hour cache
            return result
        return None
