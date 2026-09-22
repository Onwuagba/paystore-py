"""Django app config for paystore_django."""

from django.apps import AppConfig


class PaystoreDjangoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "paystore_django"
    label = "paystore_django"
    verbose_name = "Paystore"
