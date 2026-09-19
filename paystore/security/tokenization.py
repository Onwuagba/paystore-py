"""Tokenization utilities and helpers."""

from datetime import datetime, timedelta
from typing import Any, Dict


class TokenManager:
    """
    Helper class for managing payment tokens.

    This provides utilities for working with tokenized payment methods,
    including validation, expiry checking, and token metadata management.
    """

    @staticmethod
    def is_reusable(authorization: Dict[str, Any]) -> bool:
        """
        Check if an authorization token is reusable.

        Args:
            authorization: Authorization object from provider

        Returns:
            True if token can be reused for charges
        """
        return authorization.get("reusable", False)

    @staticmethod
    def is_expired(authorization: Dict[str, Any]) -> bool:
        """
        Check if a card token has expired.

        Args:
            authorization: Authorization object with exp_month and exp_year

        Returns:
            True if card has expired
        """
        exp_month = authorization.get("exp_month")
        exp_year = authorization.get("exp_year")

        if not exp_month or not exp_year:
            return False

        try:
            exp_date = datetime(int(exp_year), int(exp_month), 1)
            if exp_date.month == 12:
                exp_date = exp_date.replace(year=exp_date.year + 1, month=1)
            else:
                exp_date = exp_date.replace(month=exp_date.month + 1)

            return datetime.now() >= exp_date
        except (ValueError, TypeError):
            return False

    @staticmethod
    def get_card_info(authorization: Dict[str, Any]) -> Dict[str, Any]:
        """Extract card information from authorization object."""
        return {
            "brand": authorization.get("brand") or authorization.get("card_type"),
            "last4": authorization.get("last4"),
            "exp_month": authorization.get("exp_month"),
            "exp_year": authorization.get("exp_year"),
            "bank": authorization.get("bank"),
            "country_code": authorization.get("country_code"),
            "is_reusable": TokenManager.is_reusable(authorization),
            "is_expired": TokenManager.is_expired(authorization),
        }

    @staticmethod
    def format_card_display(authorization: Dict[str, Any]) -> str:
        """
        Format card information for display to users.

        Example:
            >>> token = {
            ...     "brand": "visa", "last4": "4242",
            ...     "exp_month": "12", "exp_year": "2025"
            ... }
            >>> TokenManager.format_card_display(token)
            'Visa •••• 4242 (Expires 12/2025)'
        """
        brand = (
            authorization.get("brand") or authorization.get("card_type") or "Card"
        ).title()
        last4 = authorization.get("last4", "****")
        exp_month = authorization.get("exp_month")
        exp_year = authorization.get("exp_year")

        display = f"{brand} •••• {last4}"

        if exp_month and exp_year:
            display += f" (Expires {exp_month}/{exp_year})"

        return display

    @staticmethod
    def filter_active_tokens(authorizations: list) -> list:
        """Filter list of authorizations to only active, usable tokens."""
        return [
            auth
            for auth in authorizations
            if TokenManager.is_reusable(auth) and not TokenManager.is_expired(auth)
        ]


class RecurringPaymentHelper:
    """Helper for managing recurring/subscription payments using tokens."""

    @staticmethod
    def calculate_next_charge_date(
        start_date: datetime, interval: str = "monthly", interval_count: int = 1
    ) -> datetime:
        """Calculate next charge date for recurring payment."""
        if interval == "daily":
            return start_date + timedelta(days=interval_count)
        elif interval == "weekly":
            return start_date + timedelta(weeks=interval_count)
        elif interval == "monthly":
            month = start_date.month + interval_count
            year = start_date.year
            while month > 12:
                month -= 12
                year += 1
            return start_date.replace(year=year, month=month)
        elif interval == "yearly":
            return start_date.replace(year=start_date.year + interval_count)
        else:
            raise ValueError(f"Invalid interval: {interval}")
