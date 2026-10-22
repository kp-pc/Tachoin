"""Tachoin wallet: Ed25519 key pair with 'tach' address prefix.

Builds on Tachyon's pure-Python Ed25519 (RFC 8032) implementation.
Addresses use Base58Check with the 'tach' prefix for human readability.
"""

from __future__ import annotations

import os
import json
import hashlib
from dataclasses import dataclass, asdict
from typing import Optional, Tuple

# Add Tachyon to path so we can import its crypto
import sys
import os
_TACHYON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tachyon-blockchain")
if _TACHYON_PATH not in sys.path:
    sys.path.insert(0, _TACHYON_PATH)

from tachyon.crypto import (
    KeyPair,
    public_key_from_seed,
    sign,
    verify,
    address_from_public_key,
    public_key_from_address,
    ADDRESS_PREFIX as TACHYON_ADDR_PREFIX,
)
from tachyon.encoding import b58encode, b58decode, digest, encode_with_checksum, decode_with_checksum

# Tachoin-specific address prefix
TACHOIN_ADDR_PREFIX = "tach"


def _tachoin_address_from_public_key(public_key: bytes) -> str:
    """Derive a tachoin address from a raw Ed25519 public key.

    The address encodes the full 32-byte public key with a 4-byte checksum,
    prefixed with 'tach'. This allows recovery of the public key for
    signature verification.
    """
    return encode_with_checksum(public_key, TACHOIN_ADDR_PREFIX)


def _tachoin_public_key_from_address(address: str) -> bytes:
    """Recover the raw 32-byte public key from a tachoin address."""
    return decode_with_checksum(address, TACHOIN_ADDR_PREFIX)


class TachoinWallet:
    """Tachoin wallet wrapping an Ed25519 key pair.

    Usage:
        wallet = TachoinWallet.generate()
        wallet = TachoinWallet.from_mnemonic(words)
        wallet = TachoinWallet.from_seed_hex(hex_str)
    """

    def __init__(self, seed: bytes):
        self._seed = seed
        self._keypair = KeyPair.from_seed(seed)

    # ---- Construction ----

    @classmethod
    def generate(cls) -> "TachoinWallet":
        """Create a new wallet with a random 256-bit seed."""
        return cls(seed=os.urandom(32))

    @classmethod
    def from_seed_hex(cls, hex_str: str) -> "TachoinWallet":
        """Restore wallet from a 64-char hex seed string."""
        return cls(seed=bytes.fromhex(hex_str))

    @classmethod
    def from_mnemonic(cls, words: str) -> "TachoinWallet":
        """Derive seed from a BIP-39 style mnemonic (simplified: SHA-512 of phrase)."""
        normalized = words.strip().lower()
        seed = hashlib.sha512(normalized.encode("utf-8")).digest()[:32]
        return cls(seed=seed)

    # ---- Address & keys ----

    @property
    def address(self) -> str:
        """Tachoin address (Base58Check with 'tach' prefix)."""
        return _tachoin_address_from_public_key(self._keypair.public_key)

    @property
    def public_key_hex(self) -> str:
        return self._keypair.public_key.hex()

    @property
    def seed_hex(self) -> str:
        """Return the 64-char hex seed (for backup)."""
        return self._seed.hex()

    # ---- Signing ----

    def sign(self, message: bytes) -> bytes:
        """Sign a message with Ed25519."""
        return self._keypair.sign(message)

    @staticmethod
    def verify(address: str, message: bytes, signature: bytes) -> bool:
        """Verify an Ed25519 signature against a tachoin address."""
        try:
            pk = _tachoin_public_key_from_address(address)
            return verify(pk, message, signature)
        except ValueError:
            return False

    # ---- Serialization ----

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "public_key": self.public_key_hex,
            "seed_hex": self.seed_hex,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @staticmethod
    def save(path: str, wallet: "TachoinWallet", passphrase: Optional[str] = None) -> None:
        """Save wallet to JSON file. Passphrase XOR-encrypts the seed."""
        data = wallet.to_dict()
        if passphrase:
            key = hashlib.sha256(passphrase.encode("utf-8")).digest()
            xor_seed = bytes(b ^ key[i % 32] for i, b in enumerate(bytes.fromhex(data["seed_hex"])))
            data["seed_hex"] = xor_seed.hex()
            data["encrypted"] = True
            data["passphrase_hint"] = True
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load(path: str, passphrase: Optional[str] = None) -> "TachoinWallet":
        """Load wallet from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        if data.get("encrypted") and passphrase:
            key = hashlib.sha256(passphrase.encode("utf-8")).digest()
            xor_seed = bytes(b ^ key[i % 32] for i, b in enumerate(bytes.fromhex(data["seed_hex"])))
            data["seed_hex"] = xor_seed.hex()
        return TachoinWallet.from_seed_hex(data["seed_hex"])
