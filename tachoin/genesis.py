"""Genesis identity and initial TACH state.

Every account in Tachoin is identified by its *tachoin* address (the
``tach``-prefixed Base58Check form), never by the underlying Tachyon
``tch``-prefixed address.  Deriving both from one seed keeps signatures and
state lookups on the same identifier.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from ._tachyon import ensure_tachyon

ensure_tachyon()

from tachyon.chain import (
    BASE_FEE_INITIAL,
    GENESIS_SLOT,
    GENESIS_TIME_MS,
    Block,
    BlockHeader,
)
from tachyon.crypto import KeyPair
from tachyon.encoding import digest
from tachyon.smt import SparseMerkleTree

from .config import (
    GENESIS_REWARD_POOL,
    STATE_KEY_BURNED_SUPPLY,
    STATE_KEY_CIRCULATING_SUPPLY,
    STATE_KEY_TOTAL_SUPPLY,
    STATE_KEY_UNCIRCULATED_SUPPLY,
    TOTAL_SUPPLY,
    UNCIRCULATED_SUPPLY,
    balance_key,
    nonce_key,
    stake_key,
)
from .wallet import address_from_seed


def int_to_bytes(value: int) -> bytes:
    """Encode a non-negative integer as minimal big-endian bytes.

    Token amounts exceed 64 bits (18 decimals over a 100M supply), so the
    fixed-width Tachyon ``u64`` helper cannot be used for balances.
    """
    if value < 0:
        raise ValueError("token amounts cannot be negative")
    if value == 0:
        return b"\x00"
    return value.to_bytes((value.bit_length() + 7) // 8, "big")


def bytes_to_int(data: bytes | None) -> int:
    """Inverse of :func:`int_to_bytes`."""
    if not data:
        return 0
    return int.from_bytes(data, "big")


def validator_addresses(validators: Sequence[KeyPair]) -> List[str]:
    """Return the canonical tachoin address of each validator."""
    return [address_from_seed(kp.seed) for kp in validators]


def genesis_allocations(validators: Sequence[KeyPair]) -> List[Tuple[str, int]]:
    """Split the genesis reward pool evenly, remainder to the last validator."""
    if not validators:
        raise ValueError("at least one validator is required")
    count = len(validators)
    per_validator = GENESIS_REWARD_POOL // count
    allocations = []
    for index, address in enumerate(validator_addresses(validators)):
        if index < count - 1:
            allocations.append((address, per_validator))
        else:
            allocations.append(
                (address, GENESIS_REWARD_POOL - per_validator * (count - 1))
            )
    return allocations


def apply_genesis_state(
    smt: SparseMerkleTree, validators: Sequence[KeyPair]
) -> List[Tuple[str, int]]:
    """Write the initial supply and per-validator balances into ``smt``."""
    smt.set(STATE_KEY_TOTAL_SUPPLY, int_to_bytes(TOTAL_SUPPLY))
    smt.set(STATE_KEY_CIRCULATING_SUPPLY, int_to_bytes(GENESIS_REWARD_POOL))
    # The unissued reserve is *uncirculated*, not burned: validators may still
    # mint from it.  Burned starts at zero and only grows via burn transactions.
    smt.set(STATE_KEY_UNCIRCULATED_SUPPLY, int_to_bytes(UNCIRCULATED_SUPPLY))
    smt.set(STATE_KEY_BURNED_SUPPLY, int_to_bytes(0))

    allocations = genesis_allocations(validators)
    for address, amount in allocations:
        # The allocation is credited to the spendable balance only.  Writing it
        # to the stake bucket as well would count the same tokens twice and
        # break ``balances + stakes == circulating``.  Consensus stake for the
        # genesis validator set is recorded on the Tachyon ledger instead.
        smt.set(balance_key(address), int_to_bytes(amount))
        smt.set(nonce_key(address), int_to_bytes(0))
    return allocations


def create_genesis_block(
    validators: Sequence[KeyPair], smt: SparseMerkleTree
) -> Block:
    """Build the genesis block over an already-populated ``smt``."""
    if not validators:
        raise ValueError("at least one validator is required")
    header = BlockHeader(
        slot=GENESIS_SLOT,
        parent_slot=-1,
        parent_hash=bytes(32),
        transactions_root=digest("empty_tx_root"),
        state_root=smt.root(),
        base_fee=BASE_FEE_INITIAL,
        leader=address_from_seed(validators[0].seed),
        timestamp=GENESIS_TIME_MS,
    )
    return Block(header=header, transactions=[])
