"""High-level Tachoin client.

Wraps a :class:`~tachoin.node.TachoinNode` with amount-aware helpers so callers
work in human-readable TACH strings instead of base units.

This is an in-process simulation harness: the validator set is created locally,
which makes it suitable for integration tests, demos and CLI runs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from ._tachyon import ensure_tachyon

ensure_tachyon()

from tachyon.crypto import KeyPair

from .node import TachoinNode, TachoinResult, format_tach, parse_tach
from .transaction import TachoinTx
from .wallet import TachoinWallet


def _result_dict(result: TachoinResult) -> Dict[str, Any]:
    """Normalise a node result into the client's dict shape."""
    return {
        "success": result.success,
        "tx_hash": result.tx_hash,
        "nonce": result.nonce,
        "new_balance": format_tach(result.new_balance),
        "error": result.error,
    }


class TachoinClient:
    """Convenience API over a local :class:`TachoinNode`."""

    def __init__(self, num_validators: int = 4):
        if num_validators < 1:
            raise ValueError("num_validators must be at least 1")
        self._validators: List[KeyPair] = [
            KeyPair.generate() for _ in range(num_validators)
        ]
        self._node = TachoinNode(self._validators)

    @classmethod
    def from_seeds(cls, seeds: Sequence[str]) -> "TachoinClient":
        """Build a client from hex validator seeds for reproducible runs."""
        if not seeds:
            raise ValueError("at least one seed is required")
        keypairs = [KeyPair.from_seed(bytes.fromhex(s)) for s in seeds]
        client = cls.__new__(cls)
        client._validators = keypairs
        client._node = TachoinNode(keypairs)
        return client

    # ---- Accessors ----------------------------------------------------

    @property
    def node(self) -> TachoinNode:
        return self._node

    def get_node(self) -> TachoinNode:
        return self._node

    def validator_seeds(self) -> List[str]:
        return [kp.seed.hex() for kp in self._validators]

    def validator_wallets(self) -> List[TachoinWallet]:
        return [TachoinWallet(seed=kp.seed) for kp in self._validators]

    def validator_addresses(self) -> List[str]:
        return self._node.validator_addresses()

    def create_wallet(self) -> TachoinWallet:
        return TachoinWallet.generate()

    # ---- Queries ------------------------------------------------------

    def balance(self, address: str) -> Dict[str, Any]:
        raw = self._node.get_balance(address)
        return {"address": address, "balance": format_tach(raw), "raw": raw}

    def stake_info(self, address: str) -> Dict[str, Any]:
        raw = self._node.get_stake(address)
        return {"address": address, "staked": format_tach(raw), "raw": raw}

    def supply(self) -> Dict[str, str]:
        return self._node.supply()

    def status(self) -> Dict[str, Any]:
        return self._node.status()

    # ---- Transactions -------------------------------------------------

    def _submit(self, builder, wallet: TachoinWallet, amount: str, *extra: Any):
        units = parse_tach(amount)
        nonce = self._node.get_nonce(wallet.address)
        slot = self._node.get_current_slot() + 1
        tx = builder(wallet, units, nonce, slot, *extra)
        return _result_dict(self._node.submit_transaction(tx))

    def transfer(self, wallet: TachoinWallet, to: str, amount: str):
        units = parse_tach(amount)
        nonce = self._node.get_nonce(wallet.address)
        slot = self._node.get_current_slot() + 1
        tx = TachoinTx.build_transfer(wallet, to, units, nonce, slot)
        return _result_dict(self._node.submit_transaction(tx))

    def mint(self, wallet: TachoinWallet, amount: str):
        return self._submit(TachoinTx.build_mint, wallet, amount)

    def burn(self, wallet: TachoinWallet, amount: str):
        return self._submit(TachoinTx.build_burn, wallet, amount)

    def stake(
        self, wallet: TachoinWallet, amount: str, validator: Optional[str] = None
    ):
        return self._submit(
            TachoinTx.build_stake, wallet, amount, validator or wallet.address
        )

    def unstake(
        self, wallet: TachoinWallet, amount: str, validator: Optional[str] = None
    ):
        return self._submit(
            TachoinTx.build_unstake, wallet, amount, validator or wallet.address
        )

    # ---- Blocks -------------------------------------------------------

    def produce_blocks(self, count: int, transactions_per_block: int = 0):
        return self._node.produce_blocks(count, transactions_per_block)
