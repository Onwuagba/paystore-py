"""Custom exceptions."""


class PaymentError(Exception):
    """Base exception for payment-related errors."""

    pass


class ProviderError(PaymentError):
    """Exception for provider-specific errors."""

    pass


class AuthenticationError(ProviderError):
    """Raised when the provider rejects the API key/credentials (401/403)."""

    pass


class RateLimitError(ProviderError):
    """Raised when the provider throttles requests (429)."""

    pass


class NetworkError(ProviderError):
    """Raised for connection failures, timeouts, or other transport errors."""

    pass


class ConfigurationError(PaymentError):
    """Exception for configuration errors."""

    pass


class ValidationError(PaymentError):
    """Exception for validation errors."""

    pass
