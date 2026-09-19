"""Minimal Django settings for testing paystore_django."""

SECRET_KEY = "test-secret-key"
USE_TZ = True
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]
DATABASES = {}
ROOT_URLCONF = "paystore_django_tests.urls"

PAYSTORE = {
    "PROVIDER": "paystack",
    "ENVIRONMENT": "sandbox",
    "API_KEY": "sk_test_mock",
    "WEBHOOK_SECRET": "whsec_mock",
}
