"""
Profit and Loss tracking module.

This module handles tracking and analysis of trading performance,
including transaction recording and P&L calculations.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import json
from decimal import Decimal
from collections import defaultdict
import asyncio
from notifications.telegram_notifications import TelegramNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Transaction:
    """Represents a single trading transaction."""
    token_address: str
    token_symbol: str
    transaction_type: str  # 'BUY' or 'SELL'
    quantity: Decimal
    price_usd: Decimal
    timestamp: datetime
    gas_fee_usd: Decimal
    transaction_hash: str
    
    def to_dict(self) -> Dict:
        """Convert transaction to dictionary."""
        return {
            **asdict(self),
            'quantity': str(self.quantity),
            'price_usd': str(self.price_usd),
            'gas_fee_usd': str(self.gas_fee_usd),
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class TradePosition:
    """Represents a complete trade (entry and exit)."""
    token_address: str
    token_symbol: str
    entry_transaction: Transaction
    exit_transaction: Optional[Transaction]
    realized_pnl: Optional[Decimal]
    roi_percentage: Optional[Decimal]
    holding_period: Optional[float]  # in hours
    status: str  # 'OPEN' or 'CLOSED'

    def to_dict(self) -> Dict:
        """Convert position to dictionary."""
        return {
            'token_address': self.token_address,
            'token_symbol': self.token_symbol,
            'entry_transaction': self.entry_transaction.to_dict(),
            'exit_transaction': self.exit_transaction.to_dict() if self.exit_transaction else None,
            'realized_pnl': str(self.realized_pnl) if self.realized_pnl is not None else None,
            'roi_percentage': str(self.roi_percentage) if self.roi_percentage is not None else None,
            'holding_period': self.holding_period,
            'status': self.status
        }

class ProfitLossTracker:
    """Tracks and analyzes trading performance."""

    def __init__(self, telegram_notifier: TelegramNotifier):
        """
        Initialize the profit/loss tracker.

        Args:
            telegram_notifier: TelegramNotifier instance for sending alerts
        """
        self.transactions: List[Transaction] = []
        self.positions: Dict[str, List[TradePosition]] = defaultdict(list)
        self.telegram_notifier = telegram_notifier
        self.total_realized_pnl = Decimal('0')
        self.total_trades = 0
        self.winning_trades = 0

    async def record_transaction(self,
                               token_address: str,
                               token_symbol: str,
                               transaction_type: str,
                               quantity: Decimal,
                               price_usd: Decimal,
                               gas_fee_usd: Decimal,
                               transaction_hash: str) -> Transaction:
        """
        Record a new transaction and update positions.

        Args:
            token_address: Token contract address
            token_symbol: Token symbol
            transaction_type: 'BUY' or 'SELL'
            quantity: Amount of tokens
            price_usd: Price per token in USD
            gas_fee_usd: Gas fee in USD
            transaction_hash: Transaction hash

        Returns:
            Transaction: Recorded transaction
        """
        transaction = Transaction(
            token_address=token_address,
            token_symbol=token_symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            price_usd=price_usd,
            timestamp=datetime.now(),
            gas_fee_usd=gas_fee_usd,
            transaction_hash=transaction_hash
        )
        
        self.transactions.append(transaction)
        
        # Update positions
        if transaction_type == 'BUY':
            position = TradePosition(
                token_address=token_address,
                token_symbol=token_symbol,
                entry_transaction=transaction,
                exit_transaction=None,
                realized_pnl=None,
                roi_percentage=None,
                holding_period=None,
                status='OPEN'
            )
            self.positions[token_address].append(position)
            
            await self._notify_new_position(position)
            
        elif transaction_type == 'SELL':
            await self._update_position_with_exit(token_address, transaction)
        
        return transaction

    async def _update_position_with_exit(self,
                                       token_address: str,
                                       exit_transaction: Transaction) -> None:
        """
        Update position with exit transaction and calculate P&L.

        Args:
            token_address: Token address
            exit_transaction: Exit (SELL) transaction
        """
        # Find the oldest open position for this token
        open_positions = [p for p in self.positions[token_address] 
                         if p.status == 'OPEN']
        
        if not open_positions:
            logger.warning(f"No open position found for token {token_address}")
            return
        
        position = open_positions[0]
        position.exit_transaction = exit_transaction
        position.status = 'CLOSED'
        
        # Calculate P&L
        entry_cost = (position.entry_transaction.quantity * 
                     position.entry_transaction.price_usd)
        exit_value = (exit_transaction.quantity * 
                     exit_transaction.price_usd)
        total_gas = (position.entry_transaction.gas_fee_usd + 
                    exit_transaction.gas_fee_usd)
        
        position.realized_pnl = exit_value - entry_cost - total_gas
        position.roi_percentage = (
            (position.realized_pnl / entry_cost) * Decimal('100')
        )
        
        # Calculate holding period
        time_diff = (exit_transaction.timestamp - 
                    position.entry_transaction.timestamp)
        position.holding_period = time_diff.total_seconds() / 3600  # Convert to hours
        
        # Update global stats
        self.total_realized_pnl += position.realized_pnl
        self.total_trades += 1
        if position.realized_pnl > 0:
            self.winning_trades += 1
        
        await self._notify_closed_position(position)

    async def _notify_new_position(self, position: TradePosition) -> None:
        """
        Send notification for new position.

        Args:
            position: New trade position
        """
        message = (
            f"🔵 New Position Opened\n"
            f"Token: {position.token_symbol}\n"
            f"Entry Price: ${float(position.entry_transaction.price_usd):.4f}\n"
            f"Quantity: {float(position.entry_transaction.quantity):.4f}\n"
            f"Total Value: ${float(position.entry_transaction.quantity * position.entry_transaction.price_usd):.2f}\n"
            f"Gas Fee: ${float(position.entry_transaction.gas_fee_usd):.2f}"
        )
        
        await self.telegram_notifier.send_message(message)

    async def _notify_closed_position(self, position: TradePosition) -> None:
        """
        Send notification for closed position.

        Args:
            position: Closed trade position
        """
        emoji = "🟢" if position.realized_pnl > 0 else "🔴"
        message = (
            f"{emoji} Position Closed\n"
            f"Token: {position.token_symbol}\n"
            f"Entry Price: ${float(position.entry_transaction.price_usd):.4f}\n"
            f"Exit Price: ${float(position.exit_transaction.price_usd):.4f}\n"
            f"Quantity: {float(position.entry_transaction.quantity):.4f}\n"
            f"P&L: ${float(position.realized_pnl):.2f} ({float(position.roi_percentage):.1f}%)\n"
            f"Holding Period: {position.holding_period:.1f} hours\n"
            f"Gas Fees: ${float(position.entry_transaction.gas_fee_usd + position.exit_transaction.gas_fee_usd):.2f}"
        )
        
        await self.telegram_notifier.send_message(message)

    async def get_performance_summary(self) -> Dict:
        """
        Get overall trading performance summary.

        Returns:
            Dict: Performance metrics
        """
        win_rate = (
            (self.winning_trades / self.total_trades * 100)
            if self.total_trades > 0 else 0
        )
        
        return {
            'total_realized_pnl': float(self.total_realized_pnl),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': win_rate,
            'average_pnl_per_trade': (
                float(self.total_realized_pnl / self.total_trades)
                if self.total_trades > 0 else 0
            )
        }

    async def send_performance_report(self) -> None:
        """Send performance report via Telegram."""
        summary = await self.get_performance_summary()
        
        message = (
            "📊 Trading Performance Report\n"
            f"Total P&L: ${summary['total_realized_pnl']:.2f}\n"
            f"Total Trades: {summary['total_trades']}\n"
            f"Win Rate: {summary['win_rate']:.1f}%\n"
            f"Average P&L per Trade: ${summary['average_pnl_per_trade']:.2f}"
        )
        
        await self.telegram_notifier.send_message(message)

    def save_to_file(self, filename: str) -> None:
        """
        Save trading history to file.

        Args:
            filename: Output filename
        """
        data = {
            'transactions': [t.to_dict() for t in self.transactions],
            'positions': {
                addr: [p.to_dict() for p in pos_list]
                for addr, pos_list in self.positions.items()
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    def load_from_file(self, filename: str) -> None:
        """
        Load trading history from file.

        Args:
            filename: Input filename
        """
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # Reset current state
        self.transactions = []
        self.positions = defaultdict(list)
        
        # Load transactions
        for t_data in data['transactions']:
            t_data['timestamp'] = datetime.fromisoformat(t_data['timestamp'])
            t_data['quantity'] = Decimal(t_data['quantity'])
            t_data['price_usd'] = Decimal(t_data['price_usd'])
            t_data['gas_fee_usd'] = Decimal(t_data['gas_fee_usd'])
            self.transactions.append(Transaction(**t_data))
        
        # Load positions
        for addr, pos_list in data['positions'].items():
            for p_data in pos_list:
                # Convert nested transactions
                entry_data = p_data['entry_transaction']
                entry_data['timestamp'] = datetime.fromisoformat(
                    entry_data['timestamp']
                )
                entry_data['quantity'] = Decimal(entry_data['quantity'])
                entry_data['price_usd'] = Decimal(entry_data['price_usd'])
                entry_data['gas_fee_usd'] = Decimal(entry_data['gas_fee_usd'])
                
                exit_data = p_data['exit_transaction']
                if exit_data:
                    exit_data['timestamp'] = datetime.fromisoformat(
                        exit_data['timestamp']
                    )
                    exit_data['quantity'] = Decimal(exit_data['quantity'])
                    exit_data['price_usd'] = Decimal(exit_data['price_usd'])
                    exit_data['gas_fee_usd'] = Decimal(exit_data['gas_fee_usd'])
                
                position = TradePosition(
                    token_address=p_data['token_address'],
                    token_symbol=p_data['token_symbol'],
                    entry_transaction=Transaction(**entry_data),
                    exit_transaction=(
                        Transaction(**exit_data) if exit_data else None
                    ),
                    realized_pnl=(
                        Decimal(p_data['realized_pnl'])
                        if p_data['realized_pnl'] else None
                    ),
                    roi_percentage=(
                        Decimal(p_data['roi_percentage'])
                        if p_data['roi_percentage'] else None
                    ),
                    holding_period=p_data['holding_period'],
                    status=p_data['status']
                )
                self.positions[addr].append(position)
