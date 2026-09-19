"""Storage interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseStorage(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def save_transaction(self, transaction: Dict[str, Any]) -> None:
        """Save transaction to storage."""
        pass


class NoOpStorage(BaseStorage):
    """Default storage that does nothing."""

    def save_transaction(self, transaction: Dict[str, Any]) -> None:
        """No-op save."""
        pass
