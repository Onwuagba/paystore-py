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
    """Validate payment amount."""
    if amount <= 0:
        raise ValidationError("Amount must be positive")
    return True
