"""Base provider abstract class."""

from abc import ABC, abstractmethod
from typing import Dict, Any
from paystore.core.config import Config


class BaseProvider(ABC):
    """Abstract base class for all payment providers."""
    
    def __init__(self, config: Config):
        self.config = config
    
    @abstractmethod
    def initialize_payment(self, amount: int, email: str, currency: str = "NGN", **kwargs: Any) -> Dict[str, Any]:
        """Initialize a payment transaction."""
        pass
    
    @abstractmethod
    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """Verify a payment transaction."""
        pass
    
    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature."""
        pass
