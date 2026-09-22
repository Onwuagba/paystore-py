"""Optional Django ORM model backing DjangoORMStorage.

Only used if you opt into DjangoORMStorage (see storage.py) — add
"paystore_django" to INSTALLED_APPS and run migrations if you do.
paystore_django works without either if you don't need persistence, or
plug in your own BaseStorage backend instead.
"""

from django.db import models


class PaystoreTransaction(models.Model):
    """
    One row per transaction result saved through DjangoORMStorage —
    written by Gateway.payments.initialize/verify/charge_authorization/
    refund whenever a Gateway is constructed with `storage=DjangoORMStorage()`.

    `raw` holds the full provider response so you're never blocked on a
    field this model doesn't expose.
    """

    reference = models.CharField(max_length=255, unique=True, db_index=True)
    provider = models.CharField(max_length=50, blank=True, default="")
    status = models.CharField(max_length=50, blank=True, default="")
    amount = models.BigIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=10, blank=True, default="")
    raw = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "paystore_django"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.reference} ({self.status or 'unknown'})"
