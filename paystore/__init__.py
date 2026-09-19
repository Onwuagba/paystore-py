"""Paystore - A unified payment gateway library."""

from paystore.__version__ import __version__
from paystore.core.exceptions import PaymentError, ProviderError
from paystore.core.gateway import Gateway

__all__ = ["__version__", "Gateway", "PaymentError", "ProviderError"]
