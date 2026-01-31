"""HTTP client wrapper."""

import httpx
from typing import Dict, Any, Optional
from paystore.core.config import Config


class HTTPClient:
    """HTTP client for making API requests."""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.Client(timeout=config.timeout)
    
    def post(self, url: str, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Make POST request."""
        response = self.client.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Make GET request."""
        response = self.client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
