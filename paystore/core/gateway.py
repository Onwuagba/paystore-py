"""Main Gateway class."""

import os
from typing import Any, Dict, Optional
from paystore.core.base_provider import BaseProvider
from paystore.core.config import Config
from paystore.core.exceptions import ConfigurationError


class Gateway:
    """
    Main gateway for payment operations.

    Credentials can be provided in multiple ways:

    1. Direct (recommended for most cases):
        gateway = Gateway(provider="paystack", api_key="sk_test_...")

    2. Environment variables (recommended for production):
        # Set PAYSTACK_SECRET_KEY in environment
        gateway = Gateway(provider="paystack")

    3. Config object:
        config = Config(provider="paystack", api_key="sk_test_...")
        gateway = Gateway(config=config)

    4. From settings/config file (Django/Flask):
        gateway = Gateway(provider=settings.PAYMENT_PROVIDER, api_key=settings.PAYMENT_API_KEY)
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        environment: str = "sandbox",
        config: Optional[Config] = None,
        **kwargs: Any
    ):
        """
        Initialize the gateway.

        Args:
            provider: Provider name (e.g., "paystack", "flutterwave")
            api_key: Provider API key (or set via environment variable)
            environment: "sandbox" or "production"
            config: Pre-configured Config object (overrides other params)
            **kwargs: Additional configuration options

        Environment variables checked (in order):
            - {PROVIDER}_SECRET_KEY (e.g., PAYSTACK_SECRET_KEY)
            - {PROVIDER}_API_KEY
            - PAYMENT_API_KEY (generic fallback)

        Raises:
            ConfigurationError: If credentials are not provided

        Examples:
            # Method 1: Direct credentials
            >>> gateway = Gateway(provider="paystack", api_key="sk_test_123")

            # Method 2: From environment
            >>> os.environ['PAYSTACK_SECRET_KEY'] = 'sk_test_123'
            >>> gateway = Gateway(provider="paystack")

            # Method 3: From Django settings
            >>> gateway = Gateway(
            ...     provider=settings.PAYMENT_PROVIDER,
            ...     api_key=settings.PAYMENT_API_KEY
            ... )
        """
        if config:
            self.config = config
        else:
            # Resolve API key from multiple sources
            resolved_api_key = self._resolve_api_key(
                provider, api_key)
            resolved_provider = provider or os.getenv(
                "PAYMENT_PROVIDER", "paystack")

            self.config = Config(
                provider=resolved_provider,
                api_key=resolved_api_key,
                environment=environment,
                **kwargs
            )

        self._provider = self._load_provider()

    def _resolve_api_key(self, provider: Optional[str], api_key: Optional[str]) -> str:
        """
        Resolve API key from multiple sources.

        Priority:
        1. Explicitly passed api_key parameter
        2. Provider-specific env var (e.g., PAYSTACK_SECRET_KEY)
        3. Generic PAYMENT_API_KEY env var
        4. Raise error if none found
        """
        if api_key:
            return api_key

        if provider:
            provider_upper = provider.upper()

            # Try provider-specific environment variables
            key = (
                os.getenv(f"{provider_upper}_SECRET_KEY") or
                os.getenv(f"{provider_upper}_API_KEY") or
                os.getenv("PAYMENT_API_KEY")
            )

            if key:
                return key

        # Try generic fallback
        generic_key = os.getenv("PAYMENT_API_KEY")
        if generic_key:
            return generic_key

        raise ConfigurationError(
            f"API key not provided. Either pass api_key parameter or set "
            f"{provider.upper() if provider else 'PROVIDER'}_SECRET_KEY environment variable."
        )

    def _load_provider(self) -> BaseProvider:
        """Load the specified provider dynamically."""
        import importlib

        provider_name = self.config.provider.lower()

        try:
            # Dynamically construct module path
            module_path = f"paystore.providers.{provider_name}.provider"
            provider_class_name = f"{provider_name.capitalize()}Provider"

            # Import the module
            module = importlib.import_module(module_path)

            # Get the provider class
            provider_class = getattr(module, provider_class_name)

            return provider_class(self.config)

        except (ImportError, AttributeError) as e:
            raise ConfigurationError(
                f"Unknown provider: {provider_name}. "
                f"Provider module not found at paystore.providers.{provider_name}.provider"
            ) from e

    @property
    def payments(self) -> "PaymentOperations":
        """Access payment operations."""
        return PaymentOperations(self._provider)


class PaymentOperations:
    """Payment operation handlers."""

    def __init__(self, provider: BaseProvider):
        self._provider = provider

    def initialize(self, amount: int, email: str, currency: str = "NGN", **kwargs: Any) -> Dict[str, Any]:
        """Initialize a payment transaction."""
        return self._provider.initialize_payment(amount=amount, email=email, currency=currency, **kwargs)

    def verify(self, reference: str) -> Dict[str, Any]:
        """Verify a payment transaction."""
        return self._provider.verify_payment(reference)
