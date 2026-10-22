"""Tachoin wallets: Ed25519 keys with ``tach``-prefixed addresses.

Addresses are Base58Check over the raw 32-byte Ed25519 public key with the
``tach`` prefix, so verifying a signature needs only the address string.

Seed backups are encrypted with scrypt (key derivation) plus an HMAC-SHA256
keystream and MAC, all from the standard library, so a wallet file is
confidential and tamper-evident without adding a dependency.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Dict, Optional

from ._tachyon import ensure_tachyon

ensure_tachyon()

from tachyon.crypto import KeyPair, public_key_from_seed, verify
from tachyon.encoding import decode_with_checksum, encode_with_checksum

#: Human-readable address prefix for every Tachoin network.
TACHOIN_ADDR_PREFIX = "tach"

SEED_SIZE = 32
_WALLET_VERSION = 1
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1


def address_from_public_key(public_key: bytes) -> str:
    """Encode a 32-byte Ed25519 public key as a tachoin address."""
    if len(public_key) != 32:
        raise ValueError("public key must be 32 bytes")
    return encode_with_checksum(public_key, TACHOIN_ADDR_PREFIX)


def public_key_from_address(address: str) -> bytes:
    """Recover the 32-byte Ed25519 public key from a tachoin address."""
    raw = decode_with_checksum(address, TACHOIN_ADDR_PREFIX)
    if len(raw) != 32:
        raise ValueError("address does not encode a public key")
    return raw


def address_from_seed(seed: bytes) -> str:
    """Derive the canonical tachoin address for a 32-byte Ed25519 seed."""
    return address_from_public_key(public_key_from_seed(bytes(seed)))


def is_valid_address(address: str) -> bool:
    """Return True when ``address`` is a well-formed tachoin address."""
    if not isinstance(address, str) or not address.startswith(TACHOIN_ADDR_PREFIX):
        return False
    try:
        public_key_from_address(address)
    except (ValueError, TypeError):
        return False
    return True


# ---- Seed encryption ---------------------------------------------------

def _derive_keys(passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
    """Derive the encryption key and MAC key from a passphrase."""
    material = hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=64,
    )
    return material[:32], material[32:]


def _keystream_xor(key: bytes, nonce: bytes, data: bytes) -> bytes:
    """XOR ``data`` with an HMAC-SHA256 counter-mode keystream."""
    out = bytearray()
    counter = 0
    while len(out) < len(data):
        block = hmac.new(
            key, nonce + counter.to_bytes(8, "big"), hashlib.sha256
        ).digest()
        out.extend(block)
        counter += 1
    return bytes(a ^ b for a, b in zip(data, out))


def _seal(passphrase: str, seed: bytes, address: str) -> Dict[str, Any]:
    """Encrypt and authenticate ``seed`` for storage."""
    salt = os.urandom(16)
    nonce = os.urandom(16)
    enc_key, mac_key = _derive_keys(passphrase, salt)
    ciphertext = _keystream_xor(enc_key, nonce, seed)
    tag = hmac.new(
        mac_key, address.encode("utf-8") + salt + nonce + ciphertext, hashlib.sha256
    ).digest()
    return {
        "salt": salt.hex(),
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex(),
        "tag": tag.hex(),
    }


def _open(passphrase: str, sealed: Dict[str, Any], address: str) -> bytes:
    """Verify and decrypt a sealed seed, raising on wrong passphrase."""
    salt = bytes.fromhex(sealed["salt"])
    nonce = bytes.fromhex(sealed["nonce"])
    ciphertext = bytes.fromhex(sealed["ciphertext"])
    tag = bytes.fromhex(sealed["tag"])
    enc_key, mac_key = _derive_keys(passphrase, salt)
    expected = hmac.new(
        mac_key, address.encode("utf-8") + salt + nonce + ciphertext, hashlib.sha256
    ).digest()
    if not hmac.compare_digest(expected, tag):
        raise ValueError("wrong passphrase or corrupted wallet file")
    return _keystream_xor(enc_key, nonce, ciphertext)


class TachoinWallet:
    """An Ed25519 key pair that can hold, sign for, and verify TACH."""

    def __init__(self, seed: bytes):
        if len(seed) != SEED_SIZE:
            raise ValueError(f"seed must be {SEED_SIZE} bytes")
        self._seed = bytes(seed)
        self._keypair = KeyPair.from_seed(self._seed)

    # ---- Construction ----

    @classmethod
    def generate(cls) -> "TachoinWallet":
        """Create a wallet from fresh OS randomness."""
        return cls(os.urandom(SEED_SIZE))

    @classmethod
    def from_seed_hex(cls, hex_str: str) -> "TachoinWallet":
        """Restore a wallet from its 64-character hex seed."""
        try:
            seed = bytes.fromhex(hex_str.strip())
        except ValueError as exc:
            raise ValueError("seed must be hexadecimal") from exc
        return cls(seed)

    @classmethod
    def from_mnemonic(cls, phrase: str) -> "TachoinWallet":
        """Derive a wallet from a passphrase-style recovery phrase.

        Not BIP-39: the phrase is hashed with SHA-512 (first 32 bytes) and the
        derivation is documented so it stays reproducible.
        """
        normalized = " ".join(phrase.lower().split())
        if not normalized:
            raise ValueError("recovery phrase must not be empty")
        digest = hashlib.sha512(normalized.encode("utf-8")).digest()
        return cls(digest[:SEED_SIZE])

    # ---- Identity ----

    @property
    def address(self) -> str:
        return address_from_public_key(self._keypair.public_key)

    @property
    def public_key(self) -> bytes:
        return self._keypair.public_key

    @property
    def public_key_hex(self) -> str:
        return self.public_key.hex()

    @property
    def seed_hex(self) -> str:
        return self._seed.hex()

    def __repr__(self) -> str:
        return f"TachoinWallet(address={self.address!r})"

    # ---- Signing ----

    def sign(self, message: bytes) -> bytes:
        return self._keypair.sign(message)

    @staticmethod
    def verify(address: str, message: bytes, signature: bytes) -> bool:
        """Verify an Ed25519 signature against a tachoin address."""
        try:
            return verify(public_key_from_address(address), message, signature)
        except (ValueError, TypeError):
            return False

    # ---- Serialization ----

    def to_dict(self) -> Dict[str, Any]:
        """Return the public view of this wallet (never the seed)."""
        return {"address": self.address, "public_key": self.public_key_hex}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def save(self, path: str, passphrase: Optional[str] = None) -> str:
        """Persist this wallet to ``path`` and return the path.

        With a passphrase the seed is encrypted and authenticated; without
        one the seed is stored as plain hex and the file is marked ``sealed:
        false`` so the lack of protection is explicit.
        """
        payload: Dict[str, Any] = {
            "version": _WALLET_VERSION,
            "address": self.address,
            "public_key": self.public_key_hex,
            "network": "tachoin",
        }
        if passphrase:
            payload["sealed"] = True
            payload["seed"] = _seal(passphrase, self._seed, self.address)
        else:
            payload["sealed"] = False
            payload["seed_hex"] = self.seed_hex
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return path

    @classmethod
    def load(cls, path: str, passphrase: Optional[str] = None) -> "TachoinWallet":
        """Load a wallet written by :meth:`save`."""
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        address = payload.get("address")
        if not address:
            raise ValueError("wallet file is missing an address")

        if payload.get("sealed"):
            if not passphrase:
                raise ValueError("wallet is sealed; a passphrase is required")
            seed = _open(passphrase, payload["seed"], address)
        else:
            seed = bytes.fromhex(payload["seed_hex"])

        wallet = cls(seed)
        if wallet.address != address:
            raise ValueError("wallet file does not match its recorded address")
        return wallet
