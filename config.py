"""
Configuration module for DeepSeeker bot.

This module contains all configuration settings for the bot,
including trading parameters, API keys, and notification settings.
"""

import os
from typing import Dict, Any
from pathlib import Path

def load_config() -> Dict[str, Any]:
    """
    Load configuration settings.

    Returns:
        Dict: Configuration dictionary
    """
    # Base directory
    base_dir = Path(__file__).parent.absolute()

    config = {
        # Telegram Configuration
        "telegram": {
            "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
            "alert_interval": 300,  # 5 minutes
            "performance_report_interval": 86400  # 24 hours
        },

        # Trading Configuration
        "trading": {
            "min_order_size": 0.001,  # Minimum order size in base currency
            "max_order_size": 0.1,    # Maximum order size in base currency
            "stop_loss_pct": 2.0,     # Stop loss percentage
            "take_profit_pct": 5.0,   # Take profit percentage
            "max_slippage_pct": 1.0,  # Maximum allowed slippage
            "min_liquidity_usd": 10000,  # Minimum liquidity in USD
            "min_volume_24h": 5000,   # Minimum 24h volume in USD
            "max_spread_pct": 3.0,    # Maximum allowed spread
        },

        # Hummingbot Configuration
        "hummingbot": {
            "instance_path": os.path.join(base_dir, "hummingbot_files"),
            "default_exchange": "binance",  # Default exchange
            "default_market": "BTC-USDT",   # Default market
            "log_level": "INFO",
            "script_enabled": True,
            "script_file": "deepseeker_strategy.py",
            "kill_switch_enabled": True,
            "kill_switch_rate": -20.0,  # Stop trading if -20% loss
        },

        # Exchange API Keys
        "exchanges": {
            "binance": {
                "api_key": os.getenv("BINANCE_API_KEY", ""),
                "api_secret": os.getenv("BINANCE_API_SECRET", ""),
                "testnet": True  # Use testnet for development
            },
            "kucoin": {
                "api_key": os.getenv("KUCOIN_API_KEY", ""),
                "api_secret": os.getenv("KUCOIN_API_SECRET", ""),
                "passphrase": os.getenv("KUCOIN_PASSPHRASE", ""),
                "testnet": True
            }
        },

        # Pattern Detection Settings
        "patterns": {
            "pump_detection": {
                "price_increase_threshold": 5.0,  # Percentage
                "volume_increase_threshold": 200.0,
                "time_window": 300  # 5 minutes
            },
            "rugpull_detection": {
                "liquidity_drop_threshold": 50.0,  # Percentage
                "time_window": 300,
                "min_liquidity_usd": 10000
            }
        },

        # Filter Settings
        "filters": {
            "min_market_cap": 100000,  # Minimum market cap in USD
            "min_holder_count": 100,   # Minimum number of holders
            "min_age_hours": 24,       # Minimum token age in hours
            "excluded_tokens": set(),  # Blacklisted tokens
            "excluded_patterns": [     # Token name patterns to exclude
                "TEST",
                "SCAM",
                "SAFE",
                "MOON",
                "ELON"
            ]
        },

        # Database Settings
        "database": {
            "path": os.path.join(base_dir, "data", "deepseeker.db"),
            "backup_path": os.path.join(base_dir, "data", "backups"),
            "backup_interval": 86400  # 24 hours
        },

        # Logging Settings
        "logging": {
            "level": "INFO",
            "file_path": os.path.join(base_dir, "logs", "deepseeker.log"),
            "max_size": 10485760,  # 10MB
            "backup_count": 5,
            "telegram_alerts": True
        }
    }

    return config

def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate configuration settings.

    Args:
        config: Configuration dictionary

    Returns:
        bool: True if configuration is valid
    """
    required_env_vars = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID"
    ]

    # Check required environment variables
    for var in required_env_vars:
        if not os.getenv(var):
            print(f"Missing required environment variable: {var}")
            return False

    # Check trading configuration
    if config["trading"]["min_order_size"] <= 0:
        print("Invalid min_order_size: must be greater than 0")
        return False

    if config["trading"]["max_order_size"] <= config["trading"]["min_order_size"]:
        print("Invalid max_order_size: must be greater than min_order_size")
        return False

    # Check pattern detection settings
    if config["patterns"]["pump_detection"]["time_window"] <= 0:
        print("Invalid pump detection time window")
        return False

    if config["patterns"]["rugpull_detection"]["time_window"] <= 0:
        print("Invalid rugpull detection time window")
        return False

    # Create necessary directories
    directories = [
        os.path.dirname(config["database"]["path"]),
        config["database"]["backup_path"],
        os.path.dirname(config["logging"]["file_path"]),
        config["hummingbot"]["instance_path"]
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)

    return True

# Load and validate configuration
config = load_config()
if not validate_config(config):
    raise ValueError("Invalid configuration")
