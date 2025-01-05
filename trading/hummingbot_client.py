"""
Hummingbot integration module.

This module provides integration with Hummingbot for automated trading
based on identified patterns and signals.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
import json
import os
import subprocess
from pathlib import Path
import aiohttp
from notifications.telegram_bot import TelegramBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HummingbotClient:
    """Client for interacting with Hummingbot."""

    def __init__(self, config: Dict, telegram_bot: TelegramBot):
        """
        Initialize Hummingbot client.

        Args:
            config: Configuration dictionary
            telegram_bot: Telegram bot instance for notifications
        """
        self.config = config
        self.telegram_bot = telegram_bot
        self.instance_path = Path(config['hummingbot']['instance_path'])
        self.config_path = self.instance_path / 'conf'
        self.strategy_path = self.instance_path / 'strategies'
        self.logs_path = self.instance_path / 'logs'
        self.running = False
        self.process = None

    async def setup(self):
        """Set up Hummingbot environment."""
        try:
            # Create necessary directories
            os.makedirs(self.config_path, exist_ok=True)
            os.makedirs(self.strategy_path, exist_ok=True)
            os.makedirs(self.logs_path, exist_ok=True)

            # Generate configuration files
            await self._generate_configs()
            
            # Create custom strategy
            await self._create_strategy()
            
            logger.info("Hummingbot environment setup complete")
            
        except Exception as e:
            logger.error(f"Failed to set up Hummingbot: {str(e)}")
            raise

    async def _generate_configs(self):
        """Generate Hummingbot configuration files."""
        # Generate main configuration
        main_config = {
            "instance_id": "deepseeker_bot",
            "log_level": "INFO",
            "kill_switch_enabled": True,
            "kill_switch_rate": -20.0,  # Stop trading if -20% loss
            "telegram_enabled": True,
            "telegram_token": self.config['telegram']['bot_token'],
            "telegram_chat_id": self.config['telegram']['chat_id'],
            "exchange_configs": {
                exchange: {
                    "api_key": details['api_key'],
                    "api_secret": details['api_secret']
                }
                for exchange, details in self.config['exchanges'].items()
            }
        }
        
        with open(self.config_path / 'conf_global.json', 'w') as f:
            json.dump(main_config, f, indent=4)

        # Generate strategy configuration
        strategy_config = {
            "strategy": "deepseeker_strategy",
            "exchange": self.config['hummingbot']['default_exchange'],
            "market": self.config['hummingbot']['default_market'],
            "min_order_size": self.config['trading']['min_order_size'],
            "max_order_size": self.config['trading']['max_order_size'],
            "order_levels": 1,
            "order_level_spread": 0.01,
            "inventory_skew_enabled": True,
            "inventory_target_base_pct": 50.0,
            "inventory_range_multiplier": 2.0,
            "filled_order_delay": 60.0,
            "hanging_orders_enabled": False,
            "position_management": {
                "stop_loss_pct": self.config['trading']['stop_loss_pct'],
                "take_profit_pct": self.config['trading']['take_profit_pct']
            }
        }
        
        with open(self.config_path / 'conf_strategy_deepseeker.json', 'w') as f:
            json.dump(strategy_config, f, indent=4)

    async def _create_strategy(self):
        """Create custom trading strategy."""
        strategy_code = '''
from decimal import Decimal
from typing import List, Tuple
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderFilledEvent
)

class DeepSeekerStrategy(StrategyBase):
    """Custom strategy for DeepSeeker bot."""
    
    def __init__(self,
                 exchange: str,
                 market: str,
                 min_order_size: Decimal,
                 max_order_size: Decimal,
                 position_management: dict):
        """Initialize strategy."""
        super().__init__()
        self.exchange = exchange
        self.market = market
        self.min_order_size = min_order_size
        self.max_order_size = max_order_size
        self.stop_loss_pct = Decimal(str(position_management["stop_loss_pct"]))
        self.take_profit_pct = Decimal(str(position_management["take_profit_pct"]))
        self.active_positions = {}

    def process_signal(self, signal_type: str, price: Decimal, confidence: Decimal):
        """
        Process trading signal.
        
        Args:
            signal_type: Type of signal (buy/sell)
            price: Current price
            confidence: Signal confidence (0-1)
        """
        if signal_type == "buy" and confidence >= Decimal("0.7"):
            self.buy(price)
        elif signal_type == "sell" and confidence >= Decimal("0.7"):
            self.sell(price)

    def buy(self, price: Decimal):
        """Execute buy order."""
        order_size = min(
            self.max_order_size,
            max(self.min_order_size, self.available_balance / price)
        )
        self.buy_with_specific_market(
            exchange=self.exchange,
            trading_pair=self.market,
            amount=order_size,
            order_type="limit",
            price=price
        )

    def sell(self, price: Decimal):
        """Execute sell order."""
        position = self.active_positions.get(self.market)
        if position:
            self.sell_with_specific_market(
                exchange=self.exchange,
                trading_pair=self.market,
                amount=position["amount"],
                order_type="limit",
                price=price
            )

    def did_fill_order(self, event: OrderFilledEvent):
        """Handle filled order event."""
        order_id = event.order_id
        if event.trade_type == "BUY":
            self.active_positions[self.market] = {
                "amount": event.amount,
                "price": event.price,
                "stop_loss": event.price * (1 - self.stop_loss_pct),
                "take_profit": event.price * (1 + self.take_profit_pct)
            }
        else:
            if self.market in self.active_positions:
                del self.active_positions[self.market]

    def manage_positions(self):
        """Manage open positions."""
        for market, position in self.active_positions.items():
            current_price = self.get_price(market)
            
            # Check stop loss
            if current_price <= position["stop_loss"]:
                self.sell(current_price)
                
            # Check take profit
            elif current_price >= position["take_profit"]:
                self.sell(current_price)
'''
        
        with open(self.strategy_path / 'deepseeker_strategy.py', 'w') as f:
            f.write(strategy_code)

    async def start(self):
        """Start Hummingbot instance."""
        if self.running:
            logger.warning("Hummingbot is already running")
            return

        try:
            # Start Hummingbot process
            cmd = [
                "hummingbot",
                "--path", str(self.instance_path),
                "--config", "conf_strategy_deepseeker.json",
                "--autostart"
            ]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.running = True
            logger.info("Hummingbot started successfully")
            
            # Start log monitoring
            asyncio.create_task(self._monitor_logs())
            
            # Notify via Telegram
            await self.telegram_bot.send_alert(
                "🤖 Hummingbot trading started",
                alert_type="general"
            )
            
        except Exception as e:
            logger.error(f"Failed to start Hummingbot: {str(e)}")
            raise

    async def stop(self):
        """Stop Hummingbot instance."""
        if not self.running:
            logger.warning("Hummingbot is not running")
            return

        try:
            # Stop the process
            if self.process:
                self.process.terminate()
                await asyncio.sleep(5)
                if self.process.poll() is None:
                    self.process.kill()
            
            self.running = False
            self.process = None
            
            logger.info("Hummingbot stopped successfully")
            
            # Notify via Telegram
            await self.telegram_bot.send_alert(
                "🛑 Hummingbot trading stopped",
                alert_type="general"
            )
            
        except Exception as e:
            logger.error(f"Failed to stop Hummingbot: {str(e)}")
            raise

    async def _monitor_logs(self):
        """Monitor Hummingbot logs for important events."""
        log_file = self.logs_path / 'hummingbot.log'
        
        while self.running:
            try:
                async with aiofiles.open(log_file) as f:
                    while True:
                        line = await f.readline()
                        if not line:
                            await asyncio.sleep(1)
                            continue
                            
                        # Process log line
                        await self._process_log_line(line)
                        
            except Exception as e:
                logger.error(f"Error monitoring logs: {str(e)}")
                await asyncio.sleep(5)

    async def _process_log_line(self, line: str):
        """
        Process Hummingbot log line.

        Args:
            line: Log line to process
        """
        try:
            # Check for trade events
            if "OrderFilledEvent" in line:
                # Extract trade details
                trade_details = self._parse_trade_event(line)
                if trade_details:
                    await self._notify_trade(trade_details)
                    
            # Check for errors
            elif "ERROR" in line:
                await self.telegram_bot.send_alert(
                    f"⚠️ Hummingbot Error: {line}",
                    alert_type="general"
                )
                
        except Exception as e:
            logger.error(f"Error processing log line: {str(e)}")

    def _parse_trade_event(self, line: str) -> Optional[Dict]:
        """
        Parse trade event from log line.

        Args:
            line: Log line to parse

        Returns:
            Dict: Trade details if found, None otherwise
        """
        try:
            # Extract relevant information
            # This is a simplified example - adjust based on actual log format
            if "BUY" in line:
                trade_type = "BUY"
            elif "SELL" in line:
                trade_type = "SELL"
            else:
                return None
                
            # Extract other details (simplified)
            parts = line.split()
            return {
                "type": trade_type,
                "symbol": parts[3],
                "amount": Decimal(parts[4]),
                "price": Decimal(parts[6]),
                "timestamp": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error parsing trade event: {str(e)}")
            return None

    async def _notify_trade(self, trade_details: Dict):
        """
        Send trade notification.

        Args:
            trade_details: Trade details
        """
        emoji = "🟢" if trade_details["type"] == "BUY" else "🔴"
        message = (
            f"{emoji} {trade_details['type']} Order Filled\n\n"
            f"Symbol: {trade_details['symbol']}\n"
            f"Amount: {trade_details['amount']:.8f}\n"
            f"Price: ${trade_details['price']:.2f}\n"
            f"Total: ${(trade_details['amount'] * trade_details['price']):.2f}"
        )
        
        await self.telegram_bot.send_alert(message, alert_type="general")
