"""HTTP client wrapper."""

import logging
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

logger = logging.getLogger("paystore.http")


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

    Logs (via the "paystore.http" logger) only the HTTP method, target
    host, and outcome — never headers, request/response bodies, or the
    full URL. Some providers (Remita) embed credentials directly in the
    URL path, so even error messages here are built from the status
    code alone, and network-layer exceptions are re-raised with
    `from None` so a raw httpx exception (whose default message can
    include the full URL) never rides along in the traceback.
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
        return self._send(
            "POST", url, lambda: self.client.post(url, json=data, headers=headers)
        )

    def post_form(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make POST request with a form-encoded body (e.g. Stripe). Not retried."""
        return self._send(
            "POST", url, lambda: self.client.post(url, data=data, headers=headers)
        )

    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Make GET request, retrying transient failures with backoff."""
        return self._send(
            "GET", url, lambda: self.client.get(url, headers=headers), retries=2
        )

    def _send(
        self,
        method: str,
        url: str,
        request_fn: Callable[[], httpx.Response],
        retries: int = 0,
    ) -> Dict[str, Any]:
        host = httpx.URL(url).host
        attempt = 0
        while True:
            logger.debug("%s %s (attempt %d)", method, host, attempt + 1)
            try:
                response = request_fn()
                response.raise_for_status()
                logger.debug("%s %s -> %d", method, host, response.status_code)
                return response.json()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (401, 403):
                    logger.error(
                        "%s %s -> %d (authentication failed)", method, host, status
                    )
                    raise AuthenticationError(
                        f"Authentication failed ({status})"
                    ) from None
                if status == 429:
                    if attempt < retries:
                        logger.warning(
                            "%s %s -> 429, retrying (attempt %d)",
                            method,
                            host,
                            attempt + 1,
                        )
                        self._backoff(attempt)
                        attempt += 1
                        continue
                    logger.error("%s %s -> 429 (rate limited, giving up)", method, host)
                    raise RateLimitError(f"Rate limited ({status})") from None
                if status >= 500 and attempt < retries:
                    logger.warning(
                        "%s %s -> %d, retrying (attempt %d)",
                        method,
                        host,
                        status,
                        attempt + 1,
                    )
                    self._backoff(attempt)
                    attempt += 1
                    continue
                logger.error("%s %s -> %d", method, host, status)
                raise ProviderError(f"Request failed ({status})") from None
            except httpx.RequestError as e:
                if attempt < retries:
                    logger.warning(
                        "%s %s network error (%s), retrying (attempt %d)",
                        method,
                        host,
                        type(e).__name__,
                        attempt + 1,
                    )
                    self._backoff(attempt)
                    attempt += 1
                    continue
                logger.error(
                    "%s %s network error (%s), giving up",
                    method,
                    host,
                    type(e).__name__,
                )
                raise NetworkError(
                    f"Network error calling {host}: {type(e).__name__}"
                ) from None

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(0.5 * (2**attempt))
