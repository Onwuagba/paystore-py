"""Helper utilities."""

import secrets
import string


def generate_reference(prefix: str = "TXN") -> str:
    """Generate unique transaction reference."""
    random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
    return f"{{prefix}}_{{random_part}}"
