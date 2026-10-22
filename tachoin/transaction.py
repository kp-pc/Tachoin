"""Signed Tachoin transactions.

A transaction names the sender, its per-account ``nonce``, one program and a
JSON payload.  The nonce is part of the signed message, so a transaction can
be included at most once: the node rejects a nonce that is not the account's
next expected value.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Tuple

from ._tachyon import ensure_tachyon

ensure_tachyon()

from tachyon.encoding import canonical_json

from .config import TRANSFER_FEE
from .wallet import TachoinWallet, is_valid_address

#: Program identifiers.  Tachyon sees them as ``tachoin_<program>``.
PROGRAM_TRANSFER = "transfer"
PROGRAM_MINT = "mint"
PROGRAM_BURN = "burn"
PROGRAM_STAKE = "stake"
PROGRAM_UNSTAKE = "unstake"

PROGRAMS = frozenset(
    {PROGRAM_TRANSFER, PROGRAM_MINT, PROGRAM_BURN, PROGRAM_STAKE, PROGRAM_UNSTAKE}
)

TACHYON_PROGRAM_PREFIX = "tachoin_"


class TransactionError(ValueError):
    """Raised when a transaction payload cannot be built or decoded."""


def _encode(**fields: Any) -> bytes:
    """Encode a payload deterministically."""
    return canonical_json(fields)


def _non_negative(value: int, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TransactionError(f"{field} must be an integer")
    if value < 0:
        raise TransactionError(f"{field} cannot be negative")
    return value


def _recipient(address: str) -> str:
    if not is_valid_address(address):
        raise TransactionError("recipient is not a valid tachoin address")
    return address


def encode_transfer(to: str, amount: int, fee: int = TRANSFER_FEE) -> bytes:
    return _encode(
        type=PROGRAM_TRANSFER,
        to=_recipient(to),
        amount=_non_negative(amount, "amount"),
        fee=_non_negative(fee, "fee"),
    )


def encode_mint(amount: int) -> bytes:
    return _encode(type=PROGRAM_MINT, amount=_non_negative(amount, "amount"))


def encode_burn(amount: int) -> bytes:
    return _encode(type=PROGRAM_BURN, amount=_non_negative(amount, "amount"))


def encode_stake(amount: int, validator: str = "") -> bytes:
    if validator:
        _recipient(validator)
    return _encode(
        type=PROGRAM_STAKE,
        amount=_non_negative(amount, "amount"),
        validator=validator,
    )


def encode_unstake(amount: int, validator: str = "") -> bytes:
    if validator:
        _recipient(validator)
    return _encode(
        type=PROGRAM_UNSTAKE,
        amount=_non_negative(amount, "amount"),
        validator=validator,
    )


def decode_payload(program: str, payload: bytes) -> Dict[str, Any]:
    """Decode and sanity-check a payload for ``program``."""
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransactionError("instruction payload is not valid JSON") from exc
    if not isinstance(data, dict) or data.get("type") != program:
        raise TransactionError(
            f"payload type does not match program {program!r}"
        )
    return data


@dataclass(frozen=True)
class TachoinTx:
    """An immutable, signable TACH transaction."""

    sender: str
    nonce: int
    program: str
    payload: bytes
    slot: int
    signature: bytes = b""

    # ---- Construction -------------------------------------------------

    def __post_init__(self) -> None:
        if self.program not in PROGRAMS:
            raise TransactionError(f"unknown program {self.program!r}")
        if not is_valid_address(self.sender):
            raise TransactionError("sender is not a valid tachoin address")
        _non_negative(self.nonce, "nonce")
        _non_negative(self.slot, "slot")

    @classmethod
    def build(
        cls,
        wallet: TachoinWallet,
        program: str,
        payload: bytes,
        nonce: int,
        slot: int,
    ) -> "TachoinTx":
        """Sign ``payload`` with ``wallet`` at the given ``nonce``."""
        unsigned = cls(
            sender=wallet.address,
            nonce=nonce,
            program=program,
            payload=payload,
            slot=slot,
        )
        return replace(unsigned, signature=wallet.sign(unsigned.message_bytes()))

    @classmethod
    def build_transfer(
        cls,
        wallet: TachoinWallet,
        to: str,
        amount: int,
        nonce: int,
        slot: int,
        fee: int = TRANSFER_FEE,
    ) -> "TachoinTx":
        return cls.build(
            wallet, PROGRAM_TRANSFER, encode_transfer(to, amount, fee), nonce, slot
        )

    @classmethod
    def build_mint(
        cls, wallet: TachoinWallet, amount: int, nonce: int, slot: int
    ) -> "TachoinTx":
        return cls.build(wallet, PROGRAM_MINT, encode_mint(amount), nonce, slot)

    @classmethod
    def build_burn(
        cls, wallet: TachoinWallet, amount: int, nonce: int, slot: int
    ) -> "TachoinTx":
        return cls.build(wallet, PROGRAM_BURN, encode_burn(amount), nonce, slot)

    @classmethod
    def build_stake(
        cls,
        wallet: TachoinWallet,
        amount: int,
        validator: str,
        nonce: int,
        slot: int,
    ) -> "TachoinTx":
        return cls.build(
            wallet, PROGRAM_STAKE, encode_stake(amount, validator), nonce, slot
        )

    @classmethod
    def build_unstake(
        cls,
        wallet: TachoinWallet,
        amount: int,
        validator: str,
        nonce: int,
        slot: int,
    ) -> "TachoinTx":
        return cls.build(
            wallet, PROGRAM_UNSTAKE, encode_unstake(amount, validator), nonce, slot
        )

    # ---- Identity -----------------------------------------------------

    def message_bytes(self) -> bytes:
        """The exact bytes covered by the signature."""
        return canonical_json(
            {
                "sender": self.sender,
                "nonce": self.nonce,
                "program": self.program,
                "payload": self.payload.hex(),
                "slot": self.slot,
            }
        )

    def tx_hash(self) -> str:
        """Stable identifier used in receipts and reports."""
        from tachyon.encoding import digest

        return digest("tachoin_tx", self.message_bytes(), self.signature).hex()

    def verify(self) -> bool:
        """Return True when the signature matches the sender address."""
        if len(self.signature) != 64:
            return False
        return TachoinWallet.verify(
            self.sender, self.message_bytes(), self.signature
        )

    def data(self) -> Dict[str, Any]:
        """Decoded payload (raises :class:`TransactionError` if malformed)."""
        return decode_payload(self.program, self.payload)

    # ---- Serialization -------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sender": self.sender,
            "nonce": self.nonce,
            "program": self.program,
            "payload": self.payload.hex(),
            "slot": self.slot,
            "signature": self.signature.hex(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TachoinTx":
        return cls(
            sender=data["sender"],
            nonce=int(data["nonce"]),
            program=data["program"],
            payload=bytes.fromhex(data["payload"]),
            slot=int(data["slot"]),
            signature=bytes.fromhex(data["signature"]),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "TachoinTx":
        return cls.from_dict(json.loads(text))

    # ---- Tachyon interoperability --------------------------------------

    def to_tachyon_transaction(self):
        """Project onto a Tachyon ``Transaction`` for the ledger/mempool."""
        from tachyon.chain import Transaction

        return Transaction(
            sender=self.sender,
            nonce=self.nonce,
            instructions=[
                (TACHYON_PROGRAM_PREFIX + self.program, self.payload)
            ],
            signature=self.signature,
            slot=self.slot,
        )

    @classmethod
    def from_tachyon_transaction(cls, tx) -> "TachoinTx":
        """Wrap a Tachyon ``Transaction`` produced by this package."""
        if len(tx.instructions) != 1:
            raise TransactionError("tachoin transactions carry exactly one instruction")
        program_id, payload = tx.instructions[0]
        if not program_id.startswith(TACHYON_PROGRAM_PREFIX):
            raise TransactionError(f"not a tachoin program: {program_id!r}")
        return cls(
            sender=tx.sender,
            nonce=tx.nonce,
            program=program_id[len(TACHYON_PROGRAM_PREFIX) :],
            payload=payload,
            slot=tx.slot,
            signature=tx.signature,
        )
