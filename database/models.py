"""
Database models for the DeepSeeker Bot.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey, Index, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from cryptography.fernet import Fernet

Base = declarative_base()

class User(Base):
    """User model for storing trader information."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True, nullable=False)
    username = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    encrypted_api_keys = Column(String)
    settings = Column(JSON)

    # Relationships
    portfolios = relationship("Portfolio", back_populates="user")
    trades = relationship("Trade", back_populates="user")

    # Indexes
    __table_args__ = (
        Index('idx_telegram_id', 'telegram_id'),
    )

class Portfolio(Base):
    """Portfolio model for tracking user assets."""
    __tablename__ = 'portfolios'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    asset = Column(String, nullable=False)
    amount = Column(Float)
    encrypted_wallet_address = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="portfolios")

    # Indexes
    __table_args__ = (
        Index('idx_user_asset', 'user_id', 'asset'),
    )

class Trade(Base):
    """Trade model for storing trade history."""
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    token_address = Column(String, nullable=False)
    token_symbol = Column(String)
    amount = Column(Float)
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    trade_type = Column(String)  # 'buy' or 'sell'
    status = Column(String)
    encrypted_tx_hash = Column(String)
    exchange = Column(String)
    pair = Column(String)
    metadata = Column(JSON)

    # Relationships
    user = relationship("User", back_populates="trades")

    # Indexes
    __table_args__ = (
        Index('idx_user_token', 'user_id', 'token_address'),
        Index('idx_timestamp', 'timestamp'),
    )

class TokenSafety(Base):
    """Model for storing token safety analysis results."""
    __tablename__ = 'token_safety'

    id = Column(Integer, primary_key=True)
    token_address = Column(String, nullable=False, unique=True)
    risk_level = Column(String)
    risk_factors = Column(JSON)
    last_checked = Column(DateTime, default=datetime.utcnow)
    is_blacklisted = Column(Boolean, default=False)
    blacklist_reason = Column(String)
    metadata = Column(JSON)

    # Indexes
    __table_args__ = (
        Index('idx_token_address', 'token_address'),
        Index('idx_risk_level', 'risk_level'),
    )
