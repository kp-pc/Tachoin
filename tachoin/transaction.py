"""Tachoin transaction types: transfer, mint, burn, stake, and unstake.

All transactions are signed with Ed25519 and carry a domain-separated payload
that integrates with Tachyon's executor and mempool.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from typing import Optional, Tuple

# Add Tachyon to path
import sys, os
_TACHYON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tachyon-blockchain")
if _TACHYON_PATH not in sys.path:
    sys.path.insert(0, _TACHYON_PATH)

from tachyon.crypto import sign, verify
from tachyon.encoding import canonical_json, digest, u64

from .config import TOKEN_DECIMALS, TRANSFER_FEE, MINT_FEE
from .wallet import TachoinWallet, _tachoin_public_key_from_address, _tachoin_address_from_public_key


# ---------- Instruction payloads ----------

def _encode_transfer(to: str, amount: int, fee: int) -> bytes:
    """Encode a transfer instruction payload."""
    return canonical_json({"type": "transfer", "to": to, "amount": amount, "fee": fee})

def _encode_mint(amount: int) -> bytes:
    """Encode a mint instruction payload."""
    return canonical_json({"type": "mint", "amount": amount})

def _encode_burn(amount: int) -> bytes:
    """Encode a burn instruction payload."""
    return canonical_json({"type": "burn", "amount": amount})

def _encode_stake(amount: int, validator: str) -> bytes:
    """Encode a stake instruction payload."""
    return canonical_json({"type": "stake", "amount": amount, "validator": validator})

def _encode_unstake(amount: int, validator: str) -> bytes:
    """Encode an unstake instruction payload."""
    return canonical_json({"type": "unstake", "amount": amount, "validator": validator})


# ---------- TachoinTx dataclass ----------

@dataclass(frozen=True)
class TachoinTx:
    """A signed Tachoin transaction.

    Wraps a Tachyon-compatible Transaction with tachoin-specific instruction
    encoding and verification helpers.
    """
    sender: str
    nonce: int
    instructions: list  # list of (program_id, payload_bytes) tuples
    signature: bytes
    slot: int

    # --- Constructors ---

    @classmethod
    def build_transfer(cls, wallet: TachoinWallet, to: str, amount: int,
                      slot: int, fee: int = TRANSFER_FEE) -> "TachoinTx":
        """Build and sign a TACH transfer transaction."""
        payload = _encode_transfer(to, amount, fee)
        tx = cls(
            sender=wallet.address,
            nonce=0,  # nonce is managed by the node per-address
            instructions=[("tachoin_transfer", payload)],
            signature=b"",
            slot=slot,
        )
        sig = wallet.sign(tx.message_bytes())
        return cls(
            sender=tx.sender, nonce=tx.nonce,
            instructions=tx.instructions, signature=sig, slot=slot,
        )

    @classmethod
    def build_mint(cls, wallet: TachoinWallet, amount: int, slot: int) -> "TachoinTx":
        """Build and sign a mint transaction (requires validator authority)."""
        payload = _encode_mint(amount)
        tx = cls(
            sender=wallet.address, nonce=0,
            instructions=[("tachoin_mint", payload)],
            signature=b"", slot=slot,
        )
        sig = wallet.sign(tx.message_bytes())
        return cls(sender=tx.sender, nonce=tx.nonce,
                   instructions=tx.instructions, signature=sig, slot=slot)

    @classmethod
    def build_burn(cls, wallet: TachoinWallet, amount: int, slot: int) -> "TachoinTx":
        """Build and sign a burn transaction."""
        payload = _encode_burn(amount)
        tx = cls(
            sender=wallet.address, nonce=0,
            instructions=[("tachoin_burn", payload)],
            signature=b"", slot=slot,
        )
        sig = wallet.sign(tx.message_bytes())
        return cls(sender=tx.sender, nonce=tx.nonce,
                   instructions=tx.instructions, signature=sig, slot=slot)

    @classmethod
    def build_stake(cls, wallet: TachoinWallet, amount: int, validator: str, slot: int) -> "TachoinTx":
        """Build and sign a stake transaction."""
        payload = _encode_stake(amount, validator)
        tx = cls(
            sender=wallet.address, nonce=0,
            instructions=[("tachoin_stake", payload)],
            signature=b"", slot=slot,
        )
        sig = wallet.sign(tx.message_bytes())
        return cls(sender=tx.sender, nonce=tx.nonce,
                   instructions=tx.instructions, signature=sig, slot=slot)

    @classmethod
    def build_unstake(cls, wallet: TachoinWallet, amount: int, validator: str, slot: int) -> "TachoinTx":
        """Build and sign an unstake transaction."""
        payload = _encode_unstake(amount, validator)
        tx = cls(
            sender=wallet.address, nonce=0,
            instructions=[("tachoin_unstake", payload)],
            signature=b"", slot=slot,
        )
        sig = wallet.sign(tx.message_bytes())
        return cls(sender=tx.sender, nonce=tx.nonce,
                   instructions=tx.instructions, signature=sig, slot=slot)

    # --- Serialization ---

    def message_bytes(self) -> bytes:
        return canonical_json({
            "sender": self.sender,
            "nonce": self.nonce,
            "instructions": [(pid, p.decode("utf-8", errors="replace")) for pid, p in self.instructions],
            "slot": self.slot,
        })

    def to_json(self) -> str:
        return json.dumps({
            "sender": self.sender,
            "nonce": self.nonce,
            "instructions": [(pid, p.decode("utf-8", errors="replace")) for pid, p in self.instructions],
            "signature": self.signature.hex(),
            "slot": self.slot,
        }, indent=2)

    @staticmethod
    def from_json(data: str) -> "TachoinTx":
        d = json.loads(data)
        return TachoinTx(
            sender=d["sender"],
            nonce=d.get("nonce", 0),
            instructions=[(pid, payload.encode("utf-8")) for pid, payload in d["instructions"]],
            signature=bytes.fromhex(d["signature"]),
            slot=d["slot"],
        )

    # --- Verification ---

    def verify(self) -> bool:
        """Verify the Ed25519 signature against the sender's tachoin address."""
        return TachoinWallet.verify(self.sender, self.message_bytes(), self.signature)

    # --- Tachyon interop ---

    def to_tachyon_transaction(self):
        """Convert to a Tachyon-compatible Transaction for the mempool/executor."""
        from tachyon.chain import Transaction
        return Transaction(
            sender=self.sender,
            nonce=self.nonce,
            instructions=list(self.instructions),
            signature=self.signature,
            slot=self.slot,
        )

    @staticmethod
    def from_tachyon_transaction(tx) -> "TachoinTx":
        """Wrap a Tachyon Transaction as a TachoinTx."""
        return TachoinTx(
            sender=tx.sender,
            nonce=tx.nonce,
            instructions=list(tx.instructions),
            signature=tx.signature,
            slot=tx.slot,
        )


def decode_instruction(payload: bytes) -> dict:
    """Decode a tachoin instruction payload back to a dict."""
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return {"raw": payload.hex()}
