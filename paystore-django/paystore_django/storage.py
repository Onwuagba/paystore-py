"""Django ORM-backed storage for paystore transaction results."""

from typing import Any, Dict

from paystore.storage.base import BaseStorage


class DjangoORMStorage(BaseStorage):
    """
    Persists every transaction result Gateway saves (initialize/verify/
    charge_authorization/refund) to a PaystoreTransaction row, keyed by
    `reference` (an upsert — the same reference re-saved, e.g. by
    initialize then verify, updates the existing row).

    Setup:
        1. Add "paystore_django" to INSTALLED_APPS.
        2. Run `python manage.py migrate`.
        3. Pass storage=DjangoORMStorage() to Gateway/AsyncGateway, or
           get_gateway(storage=DjangoORMStorage()).

    Silently skips saving if `reference` is missing from the result
    (nothing to key the row on) rather than raising — a save failure
    here shouldn't break the payment flow that triggered it.
    """

    def save_transaction(self, transaction: Dict[str, Any]) -> None:
        from paystore_django.models import PaystoreTransaction

        reference = transaction.get("reference")
        if not reference:
            return

        PaystoreTransaction.objects.update_or_create(
            reference=reference,
            defaults={
                "provider": transaction.get("provider", ""),
                "status": transaction.get("status", ""),
                "amount": transaction.get("amount"),
                "currency": transaction.get("currency", ""),
                "raw": transaction,
            },
        )
