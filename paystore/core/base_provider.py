"""Base provider abstract class."""

from abc import ABC, abstractmethod
from typing import Any, Dict, FrozenSet, List, Optional

from paystore.core.config import Config


class BaseProvider(ABC):
    """
    Abstract base class for all payment providers.

    initialize_payment, verify_payment, and verify_webhook_signature are
    required of every provider. charge_authorization, customer
    management, and token listing/deactivation are optional — a
    provider that doesn't support one should declare that in
    SUPPORTED_FEATURES (checked via Gateway.supports()) rather than
    silently accepting calls it can't fulfill.
    """

    SUPPORTED_FEATURES: FrozenSet[str] = frozenset()
    """
    Which optional features this provider implements. Valid values:
    "charge_authorization", "customers", "tokens". A provider that
    doesn't include a feature here should still override its methods to
    raise NotImplementedError with a clear message (see the defaults
    below) — SUPPORTED_FEATURES is for callers who want to check ahead
    of time via Gateway.supports() instead of catching the exception.
    """

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
        idempotency_key: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Charge a tokenized payment method.

        idempotency_key: if the provider supports native idempotency
        (currently only Stripe), passed through as a header so retrying
        with the same key is safe against duplicate charges even across
        processes. Providers without native support should accept and
        ignore it — Gateway.payments.charge_authorization still dedupes
        by this key for the lifetime of the Gateway instance.
        """
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
