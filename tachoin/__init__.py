"""Tachoin: a cryptocurrency built on the Tachyon blockchain.

Importing this package resolves the external Tachyon dependency (see
:mod:`tachoin._tachyon`), so ``import tachoin`` is always enough before using
any submodule.
"""

from __future__ import annotations

from ._tachyon import ensure_tachyon

ensure_tachyon()

from .config import (
    GENESIS_REWARD_POOL,
    TOKEN_DECIMALS,
    TOKEN_NAME,
    TOKEN_SYMBOL,
    TOTAL_SUPPLY,
    TRANSFER_FEE,
)
from .transaction import TachoinTx, TransactionError
from .wallet import TachoinWallet, address_from_seed, is_valid_address

__version__ = "1.0.1"

__all__ = [
    "GENESIS_REWARD_POOL",
    "TOKEN_DECIMALS",
    "TOKEN_NAME",
    "TOKEN_SYMBOL",
    "TOTAL_SUPPLY",
    "TRANSFER_FEE",
    "TachoinTx",
    "TachoinWallet",
    "TransactionError",
    "__version__",
    "address_from_seed",
    "is_valid_address",
]
