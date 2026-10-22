"""High-level Tachoin client API.

Wraps the TachoinNode and exposes simple methods for:
  * Creating wallets
  * Transferring TACH
  * Minting / burning TACH
  * Staking / unstaking
  * Querying state (balances, supply, blocks)
"""

from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Optional

# Add Tachyon to path
_TACHYON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tachyon-blockchain")
if _TACHYON_PATH not in sys.path:
    sys.path.insert(0, _TACHYON_PATH)

from tachyon.crypto import KeyPair

from .node import TachoinNode
from .wallet import TachoinWallet
from .transaction import TachoinTx
from .config import TOKEN_DECIMALS, TRANSFER_FEE


class TachoinClient:
    """High-level API for the Tachoin network.

    Usage:
        client = TachoinClient(num_validators=4)
        wallet = client.create_wallet()
        result = client.transfer(wallet, "tach1...", "50")
        print(result)
    """

    def __init__(self, num_validators: int = 4):
        self._validators = [KeyPair.generate() for _ in range(num_validators)]
        self._node = TachoinNode(self._validators)

    @classmethod
    def from_seeds(cls, seeds: List[str]) -> "TachoinClient":
        """Restore validators from hex seed strings."""
        kps = [KeyPair.from_seed(bytes.fromhex(s)) for s in seeds]
        return cls._from_kps(kps)

    @classmethod
    def _from_kps(cls, kps: List[KeyPair]) -> "TachoinClient":
        client = cls.__new__(cls)
        client._validators = kps
        client._node = TachoinNode(kps)
        return client

    # ---- Wallet management ----

    def create_wallet(self) -> TachoinWallet:
        """Create a new TachoinWallet."""
        return TachoinWallet.generate()

    def get_node(self) -> TachoinNode:
        return self._node

    def get_validator_addresses(self) -> List[str]:
        return [kp.address for kp in self._validators]

    # ---- Queries ----

    def balance(self, address: str) -> Dict[str, any]:
        """Get TACH balance for an address."""
        raw = self._node.get_balance(address)
        return {
            "address": address,
            "balance": self._node.format_tach(raw),
            "raw": raw,
        }

    def stake_info(self, address: str) -> Dict[str, any]:
        """Get staked TACH for an address."""
        raw = self._node.get_stake(address)
        return {
            "address": address,
            "staked": self._node.format_tach(raw),
            "raw": raw,
        }

    def supply(self) -> Dict[str, str]:
        """Get supply statistics."""
        return {
            "total": self._node.format_tach(self._node.get_total_supply()),
            "circulating": self._node.format_tach(self._node.get_circulating_supply()),
            "burned": self._node.format_tach(self._node.get_burned_supply()),
        }

    def status(self) -> Dict[str, any]:
        return self._node.status()

    # ---- Transactions ----

    def transfer(self, wallet: TachoinWallet, to: str, amount: str) -> Dict[str, any]:
        """Transfer TACH from wallet to an address.

        Args:
            wallet: sender wallet
            to: recipient tachoin address
            amount: human-readable amount, e.g. "50" or "50.123456"

        Returns:
            dict with success, tx_hash, new_balance, or error
        """
        least_units = self._node.parse_tach(amount)
        slot = self._node.get_current_slot()
        tx = TachoinTx.build_transfer(wallet, to, least_units, slot)
        result = self._node.submit_transaction(tx)
        return {
            "success": result.success,
            "tx_hash": result.tx_hash,
            "new_balance": self._node.format_tach(result.new_balance),
            "error": result.error,
        }

    def mint(self, validator_wallet: TachoinWallet, amount: str) -> Dict[str, any]:
        """Mint TACH (validator only)."""
        least_units = self._node.parse_tach(amount)
        slot = self._node.get_current_slot()
        tx = TachoinTx.build_mint(validator_wallet, least_units, slot)
        result = self._node.submit_transaction(tx)
        return {
            "success": result.success,
            "tx_hash": result.tx_hash,
            "error": result.error,
        }

    def burn(self, wallet: TachoinWallet, amount: str) -> Dict[str, any]:
        """Burn TACH from a wallet."""
        least_units = self._node.parse_tach(amount)
        slot = self._node.get_current_slot()
        tx = TachoinTx.build_burn(wallet, least_units, slot)
        result = self._node.submit_transaction(tx)
        return {
            "success": result.success,
            "tx_hash": result.tx_hash,
            "error": result.error,
        }

    def stake(self, wallet: TachoinWallet, amount: str, validator: str = "") -> Dict[str, any]:
        """Stake TACH to a validator."""
        least_units = self._node.parse_tach(amount)
        slot = self._node.get_current_slot()
        tx = TachoinTx.build_stake(wallet, least_units, validator, slot)
        result = self._node.submit_transaction(tx)
        return {
            "success": result.success,
            "tx_hash": result.tx_hash,
            "error": result.error,
        }

    def unstake(self, wallet: TachoinWallet, amount: str, validator: str = "") -> Dict[str, any]:
        """Unstake TACH from a validator."""
        least_units = self._node.parse_tach(amount)
        slot = self._node.get_current_slot()
        tx = TachoinTx.build_unstake(wallet, least_units, validator, slot)
        result = self._node.submit_transaction(tx)
        return {
            "success": result.success,
            "tx_hash": result.tx_hash,
            "error": result.error,
        }
