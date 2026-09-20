"""Input validation utilities."""

import re

from paystore.core.exceptions import ValidationError


def validate_email(email: str) -> bool:
    """Validate email address."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email: {email}")
    return True


def validate_amount(amount: int) -> bool:
    """
    Validate payment amount.

    Must be a plain int in the provider's smallest currency unit (e.g.
    kobo, cents) — not a float. A float like 10.50 almost certainly means
    the caller meant "10.50 in major units" and silently passing it
    through would send the wrong amount to the provider.
    """
    if isinstance(amount, bool) or not isinstance(amount, int):
        got = type(amount).__name__
        raise ValidationError(
            f"Amount must be an int (smallest currency unit), got {got}"
        )
    if amount <= 0:
        raise ValidationError("Amount must be positive")
    return True
