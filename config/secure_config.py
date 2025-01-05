"""
Secure configuration management module.
"""
import os
import logging
from typing import Optional, Dict, Any
from functools import lru_cache

logger = logging.getLogger(__name__)

class SecureConfig:
    """Secure configuration management."""
    
    def __init__(self):
        self._sensitive_keys = {
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHAT_ID',
            'BINANCE_API_KEY',
            'BINANCE_API_SECRET',
            'KUCOIN_API_KEY',
            'KUCOIN_API_SECRET',
            'KUCOIN_PASSPHRASE',
            'RUGCHECK_API_KEY',
            'TOKENSNIFFER_API_KEY',
            'HONEYPOT_API_KEY',
            'POSTGRES_PASSWORD'
        }
        
        # Database configuration defaults
        self._db_defaults = {
            'POSTGRES_HOST': 'localhost',
            'POSTGRES_PORT': '5432',
            'POSTGRES_USER': 'deepseekerbot',
            'POSTGRES_DB': 'deepseekerbot',
            'POSTGRES_PASSWORD': ''  # Must be set in environment
        }
        
        # Load database configuration
        for key, default in self._db_defaults.items():
            if not os.getenv(key) and key not in self._sensitive_keys:
                os.environ[key] = default

    @lru_cache(maxsize=None)
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        value = os.getenv(key, default)
        if key in self._sensitive_keys and value is None:
            logger.warning(f"Missing sensitive configuration: {key}")
        return value

    def get_redacted(self) -> Dict[str, str]:
        """
        Get redacted configuration for logging.

        Returns:
            Dict with sensitive values redacted
        """
        config = {}
        for key in os.environ:
            if key in self._sensitive_keys:
                config[key] = '[REDACTED]'
            else:
                config[key] = os.getenv(key)
        return config

    def validate_required(self) -> None:
        """Validate that all required configuration is present."""
        missing = []
        for key in self._sensitive_keys:
            if not self.get(key):
                missing.append(key)
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")

    def get_database_config(self) -> Dict[str, str]:
        """
        Get database configuration.

        Returns:
            Database configuration dictionary
        """
        return {
            key: self.get(key, default)
            for key, default in self._db_defaults.items()
        }

# Global instance
secure_config = SecureConfig()
