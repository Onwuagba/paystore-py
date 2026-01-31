"""Data models."""

from typing import Optional
from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """Payment transaction model."""
    
    reference: str
    amount: int
    currency: str = "NGN"
    status: str
    email: str
    authorization_url: Optional[str] = None
