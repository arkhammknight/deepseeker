"""
Configuration module for filters and blacklists.

This module provides configuration settings for token filters and blacklists,
allowing users to customize their filtering criteria.
"""

from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os

@dataclass
class FilterConfig:
    """Configuration settings for token filters."""
    min_market_cap: float = 50000  # $50k minimum market cap
    min_liquidity: float = 10000   # $10k minimum liquidity
    min_holders: int = 50          # Minimum number of holders
    min_coin_age_days: int = 1     # Minimum coin age in days
    max_holder_percentage: float = 0.20  # Maximum percentage a single holder can have
    min_daily_volume: float = 5000  # $5k minimum daily volume
    max_price_impact: float = 0.10  # Maximum price impact for a standard trade
    min_dex_score: float = 0.5     # Minimum DEX trust score (0-1)

@dataclass
class BlacklistConfig:
    """Configuration for blacklist settings."""
    blacklisted_tokens: List[str] = None  # List of blacklisted token addresses
    blacklisted_developers: List[str] = None  # List of blacklisted developer addresses
    blacklisted_contracts: List[str] = None  # List of blacklisted contract patterns
    blacklist_reasons: Dict[str, str] = None  # Mapping of address to reason

    def __post_init__(self):
        """Initialize empty lists if None."""
        self.blacklisted_tokens = self.blacklisted_tokens or []
        self.blacklisted_developers = self.blacklisted_developers or []
        self.blacklisted_contracts = self.blacklisted_contracts or []
        self.blacklist_reasons = self.blacklist_reasons or {}

class ConfigManager:
    """Manager for filter and blacklist configurations."""

    def __init__(self, config_path: str = 'config/filter_settings.json'):
        """
        Initialize the configuration manager.

        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self.filter_config = FilterConfig()
        self.blacklist_config = BlacklistConfig()
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    
                    # Update filter config
                    filter_data = data.get('filters', {})
                    for key, value in filter_data.items():
                        if hasattr(self.filter_config, key):
                            setattr(self.filter_config, key, value)

                    # Update blacklist config
                    blacklist_data = data.get('blacklists', {})
                    for key, value in blacklist_data.items():
                        if hasattr(self.blacklist_config, key):
                            setattr(self.blacklist_config, key, value)
            else:
                self.save_config()  # Create default config file
        except Exception as e:
            print(f"Error loading config: {str(e)}")
            self.save_config()  # Create default config on error

    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            config_data = {
                'filters': {
                    'min_market_cap': self.filter_config.min_market_cap,
                    'min_liquidity': self.filter_config.min_liquidity,
                    'min_holders': self.filter_config.min_holders,
                    'min_coin_age_days': self.filter_config.min_coin_age_days,
                    'max_holder_percentage': self.filter_config.max_holder_percentage,
                    'min_daily_volume': self.filter_config.min_daily_volume,
                    'max_price_impact': self.filter_config.max_price_impact,
                    'min_dex_score': self.filter_config.min_dex_score
                },
                'blacklists': {
                    'blacklisted_tokens': self.blacklist_config.blacklisted_tokens,
                    'blacklisted_developers': self.blacklist_config.blacklisted_developers,
                    'blacklisted_contracts': self.blacklist_config.blacklisted_contracts,
                    'blacklist_reasons': self.blacklist_config.blacklist_reasons
                }
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {str(e)}")

    def update_filter_config(self, new_config: Dict[str, Any]) -> None:
        """
        Update filter configuration.

        Args:
            new_config: Dictionary of new configuration values
        """
        for key, value in new_config.items():
            if hasattr(self.filter_config, key):
                setattr(self.filter_config, key, value)
        self.save_config()

    def update_blacklist(self, 
                        address: str, 
                        blacklist_type: str, 
                        reason: str = None,
                        remove: bool = False) -> None:
        """
        Update blacklist entries.

        Args:
            address: Address to blacklist/unblacklist
            blacklist_type: Type of blacklist ('tokens', 'developers', 'contracts')
            reason: Reason for blacklisting
            remove: If True, remove from blacklist instead of adding
        """
        blacklist_map = {
            'tokens': 'blacklisted_tokens',
            'developers': 'blacklisted_developers',
            'contracts': 'blacklisted_contracts'
        }
        
        if blacklist_type not in blacklist_map:
            raise ValueError(f"Invalid blacklist type: {blacklist_type}")

        blacklist = getattr(self.blacklist_config, blacklist_map[blacklist_type])
        
        if remove:
            if address in blacklist:
                blacklist.remove(address)
                self.blacklist_config.blacklist_reasons.pop(address, None)
        else:
            if address not in blacklist:
                blacklist.append(address)
                if reason:
                    self.blacklist_config.blacklist_reasons[address] = reason

        self.save_config()

    def get_blacklist_reason(self, address: str) -> str:
        """
        Get the reason why an address was blacklisted.

        Args:
            address: Address to check

        Returns:
            str: Reason for blacklisting or None if not found
        """
        return self.blacklist_config.blacklist_reasons.get(address)
