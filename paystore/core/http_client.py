"""HTTP client wrapper."""

import time
from typing import Any, Callable, Dict, Optional

import httpx

from paystore.core.config import Config
from paystore.core.exceptions import (
    AuthenticationError,
    NetworkError,
    ProviderError,
    RateLimitError,
)


class HTTPClient:
    """
    HTTP client for making API requests.

    Classifies failures into paystore's exception hierarchy
    (AuthenticationError, RateLimitError, NetworkError, or the generic
    ProviderError for other 4xx/5xx) so callers can distinguish
    retryable failures from permanent ones.

    Only GET requests are retried automatically (they're read-only, so
    retrying is always safe). POST requests are never retried
    automatically — retrying a charge/payment request without an
    idempotency guarantee can duplicate its side effect. Use
    Gateway.payments.charge_authorization's idempotency_key instead.
    """

    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.Client(timeout=config.timeout)

    def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make POST request with a JSON body. Not retried automatically."""
        return self._send(lambda: self.client.post(url, json=data, headers=headers))

    def post_form(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make POST request with a form-encoded body (e.g. Stripe). Not retried."""
        return self._send(lambda: self.client.post(url, data=data, headers=headers))

    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Make GET request, retrying transient failures with backoff."""
        return self._send(lambda: self.client.get(url, headers=headers), retries=2)

    def _send(
        self, request_fn: Callable[[], httpx.Response], retries: int = 0
    ) -> Dict[str, Any]:
        attempt = 0
        while True:
            try:
                response = request_fn()
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (401, 403):
                    raise AuthenticationError(
                        f"Authentication failed ({status})"
                    ) from e
                if status == 429:
                    if attempt < retries:
                        self._backoff(attempt)
                        attempt += 1
                        continue
                    raise RateLimitError(f"Rate limited ({status})") from e
                if status >= 500 and attempt < retries:
                    self._backoff(attempt)
                    attempt += 1
                    continue
                raise ProviderError(f"Request failed ({status})") from e
            except httpx.RequestError as e:
                if attempt < retries:
                    self._backoff(attempt)
                    attempt += 1
                    continue
                raise NetworkError(f"Network error: {e}") from e

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(0.5 * (2**attempt))
