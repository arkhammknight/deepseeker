"""
Configuration settings module.
"""

import os
from pathlib import Path
from typing import Dict, Any
import logging
from .secure_config import secure_config

logger = logging.getLogger(__name__)

def load_config() -> Dict[str, Any]:
    """
    Load configuration settings.

    Returns:
        Dict: Configuration dictionary
    """
    # Base directory
    base_dir = Path(__file__).parent.parent.absolute()

    config = {
        # Telegram Configuration
        "telegram": {
            "bot_token": secure_config.get_secret("TELEGRAM_BOT_TOKEN"),
            "chat_id": secure_config.get_secret("TELEGRAM_CHAT_ID"),
            "alert_interval": 300,  # 5 minutes
            "performance_report_interval": 86400  # 24 hours
        },

        # Trading Configuration
        "trading": {
            "min_order_size": 0.001,
            "max_order_size": 0.1,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 5.0,
            "max_slippage_pct": 1.0,
            "min_liquidity_usd": 10000,
            "min_volume_24h": 5000,
            "max_spread_pct": 3.0,
            "exchanges": {
                "binance": {
                    "api_key": secure_config.get_secret("BINANCE_API_KEY"),
                    "api_secret": secure_config.get_secret("BINANCE_API_SECRET"),
                    "testnet": True
                },
                "kucoin": {
                    "api_key": secure_config.get_secret("KUCOIN_API_KEY"),
                    "api_secret": secure_config.get_secret("KUCOIN_API_SECRET"),
                    "passphrase": secure_config.get_secret("KUCOIN_PASSPHRASE"),
                    "testnet": True
                }
            }
        },

        # Hummingbot Configuration
        "hummingbot": {
            "instance_path": os.path.join(base_dir, "hummingbot_files"),
            "default_exchange": "binance",
            "default_market": "BTC-USDT",
            "log_level": "INFO",
            "script_enabled": True,
            "script_file": "deepseeker_strategy.py",
            "kill_switch_enabled": True,
            "kill_switch_rate": -20.0,
        },

        # Pattern Detection Settings
        "patterns": {
            "pump_detection": {
                "price_increase_threshold": 5.0,
                "volume_increase_threshold": 200.0,
                "time_window": 300
            },
            "rugpull_detection": {
                "liquidity_drop_threshold": 50.0,
                "time_window": 300,
                "min_liquidity_usd": 10000
            }
        },

        # Filter Settings
        "filters": {
            "min_market_cap": 100000,
            "min_holder_count": 100,
            "min_age_hours": 24,
            "excluded_tokens": set(),
            "excluded_patterns": [
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
            "backup_interval": 86400
        },

        # Logging Settings
        "logging": {
            "level": "INFO",
            "file_path": os.path.join(base_dir, "logs", "deepseeker.log"),
            "max_size": 10485760,
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

    Raises:
        ValueError: If configuration is invalid
    """
    # Use secure config validation
    if not secure_config.validate_secrets():
        return False

    # Check trading configuration
    if config["trading"]["min_order_size"] <= 0:
        logger.error("Invalid min_order_size: must be greater than 0")
        return False
    if config["trading"]["max_order_size"] <= config["trading"]["min_order_size"]:
        logger.error("Invalid max_order_size: must be greater than min_order_size")
        return False

    # Check pattern detection settings
    if config["patterns"]["pump_detection"]["time_window"] <= 0:
        logger.error("Invalid pump detection time window")
        return False
    if config["patterns"]["rugpull_detection"]["time_window"] <= 0:
        logger.error("Invalid rugpull detection time window")
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
