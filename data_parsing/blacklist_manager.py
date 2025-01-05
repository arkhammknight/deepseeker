"""
Manager for user-defined token and contract blacklists.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import datetime
import aiofiles
import asyncio

logger = logging.getLogger(__name__)

class BlacklistManager:
    """Manager for token and contract blacklists."""

    def __init__(self, blacklist_file: str = "config/blacklist.json"):
        """
        Initialize the blacklist manager.

        Args:
            blacklist_file: Path to blacklist configuration file
        """
        self.blacklist_file = Path(blacklist_file)
        self.blacklist_file.parent.mkdir(exist_ok=True)
        
        self.tokens: Set[str] = set()
        self.contracts: Set[str] = set()
        self.developers: Set[str] = set()
        self.reasons: Dict[str, str] = {}
        self._lock = asyncio.Lock()
        
        # Create file if it doesn't exist
        if not self.blacklist_file.exists():
            self._save_blacklist_sync({
                "tokens": [],
                "contracts": [],
                "developers": [],
                "reasons": {}
            })
        
        self.load_blacklist_sync()

    def _save_blacklist_sync(self, data: Dict) -> None:
        """Synchronously save blacklist to file."""
        with open(self.blacklist_file, 'w') as f:
            json.dump(data, f, indent=2)

    def load_blacklist_sync(self) -> None:
        """Synchronously load blacklist from file."""
        try:
            with open(self.blacklist_file, 'r') as f:
                data = json.load(f)
                self.tokens = set(data.get("tokens", []))
                self.contracts = set(data.get("contracts", []))
                self.developers = set(data.get("developers", []))
                self.reasons = data.get("reasons", {})
        except Exception as e:
            logger.error(f"Error loading blacklist: {str(e)}")
            raise

    async def save_blacklist(self) -> None:
        """Asynchronously save blacklist to file."""
        async with self._lock:
            data = {
                "tokens": list(self.tokens),
                "contracts": list(self.contracts),
                "developers": list(self.developers),
                "reasons": self.reasons,
                "last_updated": datetime.now().isoformat()
            }
            
            async with aiofiles.open(self.blacklist_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))

    async def add_to_blacklist(
        self, 
        item: str, 
        category: str, 
        reason: Optional[str] = None
    ) -> None:
        """
        Add an item to the blacklist.

        Args:
            item: Token address, contract, or developer to blacklist
            category: Type of item ('token', 'contract', or 'developer')
            reason: Optional reason for blacklisting
        """
        async with self._lock:
            if category == "token":
                self.tokens.add(item)
            elif category == "contract":
                self.contracts.add(item)
            elif category == "developer":
                self.developers.add(item)
            else:
                raise ValueError(f"Invalid category: {category}")
            
            if reason:
                self.reasons[item] = reason
            
            await self.save_blacklist()

    async def remove_from_blacklist(self, item: str, category: str) -> None:
        """
        Remove an item from the blacklist.

        Args:
            item: Token address, contract, or developer to remove
            category: Type of item ('token', 'contract', or 'developer')
        """
        async with self._lock:
            if category == "token":
                self.tokens.discard(item)
            elif category == "contract":
                self.contracts.discard(item)
            elif category == "developer":
                self.developers.discard(item)
            else:
                raise ValueError(f"Invalid category: {category}")
            
            if item in self.reasons:
                del self.reasons[item]
            
            await self.save_blacklist()

    def is_blacklisted(self, item: str) -> bool:
        """
        Check if an item is blacklisted.

        Args:
            item: Token address, contract, or developer to check

        Returns:
            bool: True if blacklisted
        """
        return (
            item in self.tokens or 
            item in self.contracts or 
            item in self.developers
        )

    def get_blacklist_reason(self, item: str) -> Optional[str]:
        """
        Get the reason an item was blacklisted.

        Args:
            item: Token address, contract, or developer to check

        Returns:
            Optional[str]: Reason for blacklisting, if any
        """
        return self.reasons.get(item)
