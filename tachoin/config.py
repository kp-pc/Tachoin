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

# ---- Timing (inherited from Tachyon) ----------------------------------
SLOT_MS = 400
SLOTS_PER_EPOCH = 400

# ---- Addresses --------------------------------------------------------
ADDR_PREFIX = "tach"

# ---- Sparse Merkle tree keys ------------------------------------------
STATE_KEY_TOTAL_SUPPLY = b"tachoin/total_supply"
STATE_KEY_CIRCULATING_SUPPLY = b"tachoin/circulating_supply"
STATE_KEY_UNCIRCULATED_SUPPLY = b"tachoin/uncirculated_supply"
STATE_KEY_BURNED_SUPPLY = b"tachoin/burned_supply"
# Retained for readers of the pre-1.0 layout; not written by the node.
STATE_KEY_LEGACY_BURNED = b"tachoin/burned_supply"


def balance_key(address: str) -> bytes:
    """Sparse Merkle tree key holding ``address``'s spendable balance."""
    return digest("tachoin_balance", address.encode("utf-8"))


def stake_key(address: str) -> bytes:
    """Sparse Merkle tree key holding ``address``'s staked amount."""
    return digest("tachoin_stake", address.encode("utf-8"))


def nonce_key(address: str) -> bytes:
    """Sparse Merkle tree key holding ``address``'s next expected nonce."""
    return digest("tachoin_nonce", address.encode("utf-8"))
