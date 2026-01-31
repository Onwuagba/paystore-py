"""Paystore - A unified payment gateway library."""

from paystore.__version__ import __version__
from paystore.core.gateway import Gateway
from paystore.core.exceptions import PaymentError, ProviderError

__all__ = ["__version__", "Gateway", "PaymentError", "ProviderError"]
