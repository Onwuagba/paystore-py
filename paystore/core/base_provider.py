"""Base provider abstract class."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from paystore.core.config import Config


class BaseProvider(ABC):
    """Abstract base class for all payment providers."""

    def __init__(self, config: Config):
        self.config = config

    @abstractmethod
    def initialize_payment(
        self, amount: int, email: str, currency: str = "NGN", **kwargs: Any
    ) -> Dict[str, Any]:
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

    @abstractmethod
    def charge_authorization(
        self,
        authorization_code: str,
        email: str,
        amount: int,
        currency: str = "NGN",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Charge a tokenized payment method."""
        pass

    def create_customer(
        self,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Create a customer profile (optional implementation)."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support customer creation"
        )

    def get_customer(self, customer_code: str) -> Dict[str, Any]:
        """Get customer details (optional implementation)."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support customer retrieval"
        )

    def update_customer(self, customer_code: str, **kwargs: Any) -> Dict[str, Any]:
        """Update customer details (optional implementation)."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support customer updates"
        )

    def list_customer_authorizations(self, customer_code: str) -> List[Dict[str, Any]]:
        """List payment tokens for customer (optional implementation)."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support listing authorizations"
        )

    def deactivate_authorization(self, authorization_code: str) -> Dict[str, Any]:
        """Deactivate a payment token (optional implementation)."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support deactivating authorizations"
        )
