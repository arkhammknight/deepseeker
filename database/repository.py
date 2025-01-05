"""
Repository pattern implementation for database operations.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, Portfolio, Trade, TokenSafety
from .database import Database

class Repository:
    """Base repository with common database operations."""

    def __init__(self, db: Database):
        """
        Initialize repository.

        Args:
            db: Database instance
        """
        self.db = db

class UserRepository(Repository):
    """Repository for user-related operations."""

    async def create_user(self, session: AsyncSession, telegram_id: str, username: Optional[str] = None) -> User:
        """Create new user."""
        user = User(
            telegram_id=telegram_id,
            username=username
        )
        session.add(user)
        await session.flush()
        return user

    async def get_user_by_telegram_id(self, session: AsyncSession, telegram_id: str) -> Optional[User]:
        """Get user by Telegram ID."""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def update_user_api_keys(self, session: AsyncSession, user_id: int, api_keys: Dict[str, str]) -> None:
        """Update user's encrypted API keys."""
        encrypted_keys = self.db.encrypt_data(str(api_keys))
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(encrypted_api_keys=encrypted_keys)
        )

class PortfolioRepository(Repository):
    """Repository for portfolio-related operations."""

    async def update_portfolio(
        self,
        session: AsyncSession,
        user_id: int,
        asset: str,
        amount: float,
        wallet_address: Optional[str] = None
    ) -> Portfolio:
        """Update or create portfolio entry."""
        query = select(Portfolio).where(
            Portfolio.user_id == user_id,
            Portfolio.asset == asset
        )
        result = await session.execute(query)
        portfolio = result.scalar_one_or_none()

        if portfolio:
            portfolio.amount = amount
            if wallet_address:
                portfolio.encrypted_wallet_address = self.db.encrypt_data(wallet_address)
        else:
            portfolio = Portfolio(
                user_id=user_id,
                asset=asset,
                amount=amount,
                encrypted_wallet_address=self.db.encrypt_data(wallet_address) if wallet_address else None
            )
            session.add(portfolio)

        await session.flush()
        return portfolio

    async def get_user_portfolio(self, session: AsyncSession, user_id: int) -> List[Portfolio]:
        """Get user's portfolio."""
        result = await session.execute(
            select(Portfolio).where(Portfolio.user_id == user_id)
        )
        return result.scalars().all()

class TradeRepository(Repository):
    """Repository for trade-related operations."""

    async def create_trade(
        self,
        session: AsyncSession,
        user_id: int,
        token_address: str,
        amount: float,
        price: float,
        trade_type: str,
        **kwargs
    ) -> Trade:
        """Create new trade record."""
        trade = Trade(
            user_id=user_id,
            token_address=token_address,
            amount=amount,
            price=price,
            trade_type=trade_type,
            **kwargs
        )
        
        if kwargs.get('tx_hash'):
            trade.encrypted_tx_hash = self.db.encrypt_data(kwargs['tx_hash'])
            
        session.add(trade)
        await session.flush()
        return trade

    async def get_user_trades(
        self,
        session: AsyncSession,
        user_id: int,
        token_address: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Trade]:
        """Get user's trade history."""
        query = select(Trade).where(Trade.user_id == user_id)
        
        if token_address:
            query = query.where(Trade.token_address == token_address)
        if start_time:
            query = query.where(Trade.timestamp >= start_time)
        if end_time:
            query = query.where(Trade.timestamp <= end_time)
            
        query = query.order_by(Trade.timestamp.desc())
        result = await session.execute(query)
        return result.scalars().all()

class TokenSafetyRepository(Repository):
    """Repository for token safety-related operations."""

    async def update_token_safety(
        self,
        session: AsyncSession,
        token_address: str,
        risk_level: str,
        risk_factors: List[str],
        is_blacklisted: bool = False,
        blacklist_reason: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> TokenSafety:
        """Update or create token safety record."""
        query = select(TokenSafety).where(TokenSafety.token_address == token_address)
        result = await session.execute(query)
        token_safety = result.scalar_one_or_none()

        if token_safety:
            token_safety.risk_level = risk_level
            token_safety.risk_factors = risk_factors
            token_safety.is_blacklisted = is_blacklisted
            token_safety.blacklist_reason = blacklist_reason
            token_safety.metadata = metadata
            token_safety.last_checked = datetime.utcnow()
        else:
            token_safety = TokenSafety(
                token_address=token_address,
                risk_level=risk_level,
                risk_factors=risk_factors,
                is_blacklisted=is_blacklisted,
                blacklist_reason=blacklist_reason,
                metadata=metadata
            )
            session.add(token_safety)

        await session.flush()
        return token_safety

    async def get_token_safety(self, session: AsyncSession, token_address: str) -> Optional[TokenSafety]:
        """Get token safety analysis."""
        result = await session.execute(
            select(TokenSafety).where(TokenSafety.token_address == token_address)
        )
        return result.scalar_one_or_none()
