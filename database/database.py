"""
Database connection and management module.
"""
import os
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from contextlib import asynccontextmanager
from cryptography.fernet import Fernet
import logging

from .models import Base
from ..config.secure_config import SecureConfig

logger = logging.getLogger(__name__)

class Database:
    """Database connection manager."""

    def __init__(self, config: SecureConfig):
        """
        Initialize database connection.

        Args:
            config: Secure configuration instance
        """
        self.config = config
        self.encryption_key = self._get_or_create_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        
        # Create async database engine
        self.engine = create_async_engine(
            self._get_database_url(),
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            echo=False
        )
        
        # Create async session factory
        self.async_session = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for sensitive data."""
        key_path = os.path.join(os.path.dirname(__file__), '.encryption_key')
        
        if os.path.exists(key_path):
            with open(key_path, 'rb') as f:
                return f.read()
        
        # Generate new key if none exists
        key = Fernet.generate_key()
        with open(key_path, 'wb') as f:
            f.write(key)
        return key

    def _get_database_url(self) -> str:
        """Get database URL from configuration."""
        host = self.config.get('POSTGRES_HOST', 'localhost')
        port = self.config.get('POSTGRES_PORT', '5432')
        user = self.config.get('POSTGRES_USER', 'deepseekerbot')
        password = self.config.get('POSTGRES_PASSWORD', '')
        database = self.config.get('POSTGRES_DB', 'deepseekerbot')

        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"

    @asynccontextmanager
    async def get_session(self) -> AsyncSession:
        """Get database session."""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database error: {str(e)}")
                raise
            finally:
                await session.close()

    async def initialize(self) -> None:
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        if not data:
            return ""
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        if not encrypted_data:
            return ""
        return self.fernet.decrypt(encrypted_data.encode()).decode()

    async def close(self) -> None:
        """Close database connection."""
        await self.engine.dispose()
