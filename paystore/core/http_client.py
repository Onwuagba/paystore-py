"""HTTP client wrapper."""

from typing import Any, Dict, Optional

import httpx

from paystore.core.config import Config


class HTTPClient:
    """HTTP client for making API requests."""

    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.Client(timeout=config.timeout)

    def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make POST request with a JSON body."""
        response = self.client.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()

    def post_form(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make POST request with a form-encoded body (required by e.g. Stripe)."""
        response = self.client.post(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json()

    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Make GET request."""
        response = self.client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
