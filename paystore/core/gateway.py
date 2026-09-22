"""Main Gateway class."""

import os
from typing import Any, Dict, Optional

from paystore.core.base_provider import BaseProvider
from paystore.core.config import Config
from paystore.core.exceptions import ConfigurationError
from paystore.security.validation import validate_amount, validate_email
from paystore.storage.base import BaseStorage, NoOpStorage


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
        gateway = Gateway(
            provider=settings.PAYMENT_PROVIDER,
            api_key=settings.PAYMENT_API_KEY
        )
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        environment: str = "sandbox",
        config: Optional[Config] = None,
        storage: Optional[BaseStorage] = None,
        **kwargs: Any,
    ):
        """
        Initialize the gateway.

        Args:
            provider: Provider name (e.g., "paystack", "flutterwave")
            api_key: Provider API key (or set via environment variable)
            environment: "sandbox" or "production"
            config: Pre-configured Config object (overrides other params)
            storage: Optional BaseStorage backend to persist transaction
                results from initialize/verify/charge_authorization
                (defaults to NoOpStorage, which does nothing)
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
            resolved_api_key = self._resolve_api_key(provider, api_key)
            resolved_provider = provider or os.getenv("PAYMENT_PROVIDER")

            if not resolved_provider:
                raise ConfigurationError("Provider not specified")

            if "webhook_secret" not in kwargs:
                resolved_webhook_secret = self._resolve_webhook_secret(
                    resolved_provider
                )
                if resolved_webhook_secret:
                    kwargs["webhook_secret"] = resolved_webhook_secret

            self.config = Config(
                provider=resolved_provider,
                api_key=resolved_api_key,
                environment=environment,
                **kwargs,
            )

        self.storage = storage or NoOpStorage()
        self._idempotency_cache: Dict[str, Dict[str, Any]] = {}
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
                os.getenv(f"{provider_upper}_SECRET_KEY")
                or os.getenv(f"{provider_upper}_API_KEY")
                or os.getenv("PAYMENT_API_KEY")
            )

            if key:
                return key

        # Try generic fallback
        generic_key = os.getenv("PAYMENT_API_KEY")
        if generic_key:
            return generic_key

        raise ConfigurationError(
            f"API key not provided. Either pass api_key parameter or set "
            f"{provider.upper() if provider else 'PROVIDER'}_SECRET_KEY "
            f"environment variable."
        )

    def _resolve_webhook_secret(self, provider: str) -> Optional[str]:
        """Resolve webhook secret from provider-specific or generic env vars."""
        provider_upper = provider.upper()
        return os.getenv(f"{provider_upper}_WEBHOOK_SECRET") or os.getenv(
            "PAYMENT_WEBHOOK_SECRET"
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
                f"Provider module not found at "
                f"paystore.providers.{provider_name}.provider"
            ) from e

    @property
    def payments(self) -> "PaymentOperations":
        """Access payment operations."""
        return PaymentOperations(self._provider, self.storage, self._idempotency_cache)

    @property
    def customers(self) -> "CustomerOperations":
        """Access customer operations."""
        return CustomerOperations(self._provider)

    @property
    def tokens(self) -> "TokenOperations":
        """Access tokenization operations."""
        return TokenOperations(self._provider)

    @property
    def subscriptions(self) -> "SubscriptionOperations":
        """Access recurring billing (plans/subscriptions) operations."""
        return SubscriptionOperations(self._provider)

    @property
    def transfers(self) -> "TransferOperations":
        """Access transfer/payout operations."""
        return TransferOperations(self._provider)

    @property
    def subaccounts(self) -> "SubaccountOperations":
        """Access split-payment (subaccount) operations."""
        return SubaccountOperations(self._provider)

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Verify a webhook signature for this gateway's provider.

        Raises PaymentError if the signature is invalid.
        """
        from paystore.webhooks.verifier import WebhookVerifier

        return WebhookVerifier(self._provider).verify(payload, signature)

    def supports(self, feature: str) -> bool:
        """
        Check whether the active provider supports an optional feature,
        instead of calling it and catching NotImplementedError.

        Args:
            feature: one of "charge_authorization", "customers", "tokens",
                "refunds", "subscriptions", "transfers",
                "split_payments". initialize/verify/webhook
                verification are supported by every provider and aren't
                part of this check.

        Example:
            >>> if gateway.supports("customers"):
            ...     gateway.customers.create(email="a@example.com")
        """
        return feature in self._provider.SUPPORTED_FEATURES


class CustomerOperations:
    """Customer management operations."""

    def __init__(self, provider: BaseProvider):
        self._provider = provider

    def create(
        self,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Create a customer profile."""
        validate_email(email)
        return self._provider.create_customer(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            **kwargs,
        )

    def get(self, customer_code: str) -> Dict[str, Any]:
        """Get customer details by customer code."""
        return self._provider.get_customer(customer_code)

    def update(self, customer_code: str, **kwargs: Any) -> Dict[str, Any]:
        """Update customer details."""
        return self._provider.update_customer(customer_code, **kwargs)


class TokenOperations:
    """Tokenization operations."""

    def __init__(self, provider: BaseProvider):
        self._provider = provider

    def list_for_customer(self, customer_code: str) -> list:
        """List all payment tokens for a customer."""
        return self._provider.list_customer_authorizations(customer_code)

    def deactivate(self, authorization_code: str) -> Dict[str, Any]:
        """Deactivate/delete a payment token."""
        return self._provider.deactivate_authorization(authorization_code)


class SubscriptionOperations:
    """Recurring billing (plans/subscriptions) operations."""

    def __init__(self, provider: BaseProvider):
        self._provider = provider

    def create_plan(
        self,
        name: str,
        amount: int,
        interval: str,
        currency: str = "NGN",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a recurring billing plan.

        `interval`'s valid values are provider-specific (e.g. Paystack
        wants "monthly", Stripe wants "month") and are passed straight
        through — check the active provider's docs/docstring.
        """
        validate_amount(amount)
        return self._provider.create_plan(
            name=name, amount=amount, interval=interval, currency=currency, **kwargs
        )

    def subscribe(self, customer: str, plan: str, **kwargs: Any) -> Dict[str, Any]:
        """Subscribe a customer (customer code/id) to a plan (plan code/id)."""
        return self._provider.create_subscription(
            customer=customer, plan=plan, **kwargs
        )

    def cancel(self, subscription_code: str, **kwargs: Any) -> Dict[str, Any]:
        """Cancel a subscription."""
        return self._provider.cancel_subscription(subscription_code, **kwargs)


class TransferOperations:
    """Transfer/payout operations (sending money out)."""

    def __init__(self, provider: BaseProvider):
        self._provider = provider

    def create_recipient(
        self,
        name: str,
        account_number: str,
        bank_code: str,
        currency: str = "NGN",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Register a bank account to send payouts to.

        Not every provider needs this as a separate step — check
        gateway.supports("transfers") and the active provider's
        docstring; some accept bank details directly in initiate().
        """
        return self._provider.create_transfer_recipient(
            name=name,
            account_number=account_number,
            bank_code=bank_code,
            currency=currency,
            **kwargs,
        )

    def initiate(
        self,
        recipient: Any,
        amount: int,
        reason: str = "",
        currency: str = "NGN",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Send a payout.

        `recipient` is provider-specific: a recipient code from
        create_recipient() for providers that need one, or bank account
        details directly for providers that don't.
        """
        validate_amount(amount)
        return self._provider.initiate_transfer(
            recipient=recipient,
            amount=amount,
            reason=reason,
            currency=currency,
            **kwargs,
        )


class SubaccountOperations:
    """Split-payment (subaccount) operations."""

    def __init__(self, provider: BaseProvider):
        self._provider = provider

    def create(
        self, business_name: str, account_number: str, bank_code: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Create a subaccount for split payments.

        Once created, pass the returned subaccount id/code to
        gateway.payments.initialize(...) via a provider-specific kwarg
        (e.g. Paystack's `subaccount`, Flutterwave's `subaccounts`) —
        see the active provider's docstring for the exact shape.
        """
        return self._provider.create_subaccount(
            business_name=business_name,
            account_number=account_number,
            bank_code=bank_code,
            **kwargs,
        )


class PaymentOperations:
    """Payment operation handlers."""

    def __init__(
        self,
        provider: BaseProvider,
        storage: Optional[BaseStorage] = None,
        idempotency_cache: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self._provider = provider
        self._storage = storage or NoOpStorage()
        self._idempotency_cache = (
            idempotency_cache if idempotency_cache is not None else {}
        )

    def initialize(
        self, amount: int, email: str, currency: str = "NGN", **kwargs: Any
    ) -> Dict[str, Any]:
        """Initialize a payment transaction."""
        validate_amount(amount)
        validate_email(email)
        result = self._provider.initialize_payment(
            amount=amount, email=email, currency=currency, **kwargs
        )
        self._storage.save_transaction(result)
        return result

    def verify(self, reference: str) -> Dict[str, Any]:
        """Verify a payment transaction."""
        result = self._provider.verify_payment(reference)
        self._storage.save_transaction(result)
        return result

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
        Charge a tokenized card using authorization code.

        Args:
            authorization_code: Token from previous successful transaction
            email: Customer email
            amount: Amount to charge (in smallest currency unit)
            currency: Currency code
            idempotency_key: Optional caller-supplied key. If a charge
                with this key already succeeded on this Gateway instance,
                the cached result is returned instead of charging again —
                protects against double-charging on retry (e.g. a cron
                job re-running after a network blip). Also forwarded to
                the provider natively when it supports it (Stripe).
            **kwargs: Additional provider-specific parameters

        Returns:
            Transaction details
        """
        validate_amount(amount)
        validate_email(email)

        if idempotency_key and idempotency_key in self._idempotency_cache:
            return self._idempotency_cache[idempotency_key]

        result = self._provider.charge_authorization(
            authorization_code=authorization_code,
            email=email,
            amount=amount,
            currency=currency,
            idempotency_key=idempotency_key,
            **kwargs,
        )

        if idempotency_key:
            self._idempotency_cache[idempotency_key] = result
        self._storage.save_transaction(result)
        return result

    def refund(
        self, reference: str, amount: Optional[int] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Refund a payment, in full or in part.

        Args:
            reference: the reference returned by initialize/
                charge_authorization (or verify).
            amount: partial refund amount (smallest currency unit); the
                full amount is refunded if omitted.
        """
        if amount is not None:
            validate_amount(amount)
        result = self._provider.refund_payment(reference, amount=amount, **kwargs)
        self._storage.save_transaction(result)
        return result
