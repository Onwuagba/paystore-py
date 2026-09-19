"""Signals emitted by paystore_django."""

import django.dispatch

webhook_verified = django.dispatch.Signal()
"""Sent after a webhook's signature has been verified.

Provides keyword arguments: `provider` (str) and `event` (dict, the
parsed JSON body).
"""
