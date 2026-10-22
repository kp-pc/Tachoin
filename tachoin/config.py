"""Tachoin protocol constants and state-key helpers.

Supply invariant, enforced by the node and checked in tests::

    circulating + uncirculated + burned == TOTAL_SUPPLY

* ``circulating``   - spendable TACH held in account balances.
* ``uncirculated``  - reserve the validator set may mint from.
* ``burned``        - permanently destroyed TACH.

Every key written into the Tachyon sparse Merkle tree is derived here, so
balance, stake and nonce lookups can never drift from their writers.
"""

from __future__ import annotations

from ._tachyon import ensure_tachyon

ensure_tachyon()

from tachyon.encoding import digest

# ---- Network identity -------------------------------------------------
NETWORK_ID = "tachoin-mainnet"
TESTNET_ID = "tachoin-testnet"

# ---- Token metadata ---------------------------------------------------
TOKEN_NAME = "Tachoin"
TOKEN_SYMBOL = "TACH"
TOKEN_DECIMALS = 18

# Display precision used by the CLI and ``format_tach``.
DISPLAY_DECIMALS = 6

# ---- Supply -----------------------------------------------------------
# 100,000,000 TACH expressed in base units (10**18 per TACH).
TOTAL_SUPPLY = 100_000_000 * (10 ** TOKEN_DECIMALS)

# Minted into account balances at genesis and distributed to validators.
GENESIS_REWARD_POOL = 1_000_000 * (10 ** TOKEN_DECIMALS)

# Held back for validator issuance; see ``TachoinNode.mint``.
UNCIRCULATED_SUPPLY = TOTAL_SUPPLY - GENESIS_REWARD_POOL

# ---- Staking ----------------------------------------------------------
MIN_STAKE = 100 * (10 ** TOKEN_DECIMALS)
MAX_STAKE = 10_000_000 * (10 ** TOKEN_DECIMALS)
STAKE_REWARD_RATE = 0.05
UNSTAKE_COOLDOWN_SLOTS = 400

# ---- Fees -------------------------------------------------------------
TRANSFER_FEE = 1_000
MINT_FEE = 0

# ---- Amount bounds ---------------------------------------------------
#: Maximum value that may be transferred or minted in a single transaction.
#: Prevents integer overflow in the underlying Tachyon transport which may
#: not handle extremely large integers gracefully.  Capped to the total
#: supply so a single transfer cannot exceed the entire token economy.
MAX_TRANSFER_AMOUNT = TOTAL_SUPPLY // 2

# ---- Security limits --------------------------------------------------
#: Maximum number of transactions that may sit in the pending mempool before
#: a new submission is rejected.  Prevents unbounded memory growth from
#: mempool flooding attacks.
MAX_PENDING_TXS = 10_000

#: How far ahead of the current slot a transaction may be signed before it is
#: rejected as stale.  A transaction signed for a slot more than this many
#: slots in the past is not accepted, preventing replay of old, low-fee
#: transactions that skipped the mandatory fee.
SLOT_FRESHNESS_SLOTS = 2

# ---- Timing (inherited from Tachyon) ----------------------------------
SLOT_MS = 400
SLOTS_PER_EPOCH = 400

# ---- Addresses --------------------------------------------------------
ADDR_PREFIX = "tach"

# ---- Sparse Merkle tree keys ------------------------------------------
#
# Tachyon's SMT is a 256-bit tree: ``_key_to_path`` walks every bit of the key
# and ``set`` climbs exactly 256 levels. A key of any other length therefore
# produces a commitment whose path length does not match the tree, and current
# Tachyon rejects it outright with ``SMT key must be exactly 32 bytes``.
#
# Every key is derived through :func:`tachyon.encoding.digest`, never written as
# a literal, so its length is guaranteed by construction.
def _state_key(name: str) -> bytes:
    """Derive a 32-byte sparse Merkle tree key for a protocol-level counter."""
    return digest("tachoin_state", name.encode("utf-8"))


STATE_KEY_TOTAL_SUPPLY = _state_key("total_supply")
STATE_KEY_CIRCULATING_SUPPLY = _state_key("circulating_supply")
STATE_KEY_UNCIRCULATED_SUPPLY = _state_key("uncirculated_supply")
STATE_KEY_BURNED_SUPPLY = _state_key("burned_supply")
# Retained for readers of the pre-1.0 layout; not written by the node.
STATE_KEY_LEGACY_BURNED = STATE_KEY_BURNED_SUPPLY


def balance_key(address: str) -> bytes:
    """Sparse Merkle tree key holding ``address``'s spendable balance."""
    return digest("tachoin_balance", address.encode("utf-8"))


def stake_key(address: str) -> bytes:
    """Sparse Merkle tree key holding the total TACH ``address`` has staked."""
    return digest("tachoin_stake", address.encode("utf-8"))


def validator_stake_key(address: str) -> bytes:
    """Sparse Merkle tree key holding the total TACH delegated to ``address``.

    This is the election-weight source: when a staker delegates to a validator,
    the validator's stake key is incremented, not the staker's.  The Tachyon
    ledger is synchronised from this key at block-production time, so the SMT
    remains the single source of truth for election weights.
    """
    return digest("tachoin_validator_stake", address.encode("utf-8"))


def nonce_key(address: str) -> bytes:
    """Sparse Merkle tree key holding ``address``'s next expected nonce."""
    return digest("tachoin_nonce", address.encode("utf-8"))


def delegation_key(delegator: str, validator: str) -> bytes:
    """Sparse Merkle tree key holding TACH ``delegator`` has staked with ``validator``.

    This enables per-validator unstake validation and prevents cross-validator
    stake manipulation.
    """
    return digest(
        "tachoin_delegation",
        f"{delegator}:{validator}".encode("utf-8")
    )
