"""Custom exceptions."""


class PaymentError(Exception):
    """Base exception for payment-related errors."""
    pass


class ProviderError(PaymentError):
    """Exception for provider-specific errors."""
    pass


class ConfigurationError(PaymentError):
    """Exception for configuration errors."""
    pass


class ValidationError(PaymentError):
    """Exception for validation errors."""
    pass
