"""Tachoin exception hierarchy."""

from __future__ import annotations
class TransactionError(ValueError):
    """Raised when a transaction payload cannot be built or decoded."""