"""Genesis block creation and initial state setup for Tachoin."""

from __future__ import annotations

import time
from typing import Dict, List

# Add Tachyon to path
import sys, os
_TACHYON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tachyon-blockchain")
if _TACHYON_PATH not in sys.path:
    sys.path.insert(0, _TACHYON_PATH)

from tachyon.chain import Ledger, BlockHeader, Block, Vote, GENESIS_SLOT, GENESIS_TIME_MS, BASE_FEE_INITIAL
from tachyon.crypto import KeyPair
from tachyon.smt import SparseMerkleTree
from tachyon.encoding import digest

from .config import (
    TOTAL_SUPPLY,
    GENESIS_REWARD_POOL,
    STATE_KEY_TOTAL_SUPPLY,
    STATE_KEY_CIRCULATING_SUPPLY,
    STATE_KEY_BURNED_SUPPLY,
    balance_key,
    stake_key,
    nonce_key,
)


def _int_to_bytes(value: int) -> bytes:
    """Encode a non-negative integer to big-endian bytes."""
    if value == 0:
        return b"\x00"
    return value.to_bytes((value.bit_length() + 7) // 8, "big")


def create_genesis_block(validators: List[KeyPair], smt: SparseMerkleTree) -> Block:
    """Create the genesis block for Tachoin.

    Distributes the genesis reward pool among validators and sets the initial
    total supply in the SMT state.
    """
    # Store total supply
    smt.set(STATE_KEY_TOTAL_SUPPLY, _int_to_bytes(TOTAL_SUPPLY))
    smt.set(STATE_KEY_CIRCULATING_SUPPLY, _int_to_bytes(GENESIS_REWARD_POOL))
    smt.set(STATE_KEY_BURNED_SUPPLY, _int_to_bytes(TOTAL_SUPPLY - GENESIS_REWARD_POOL))

    # Distribute genesis pool among validators
    per_validator = GENESIS_REWARD_POOL // len(validators)
    for i, kp in enumerate(validators):
        amount = per_validator if i < len(validators) - 1 else GENESIS_REWARD_POOL - per_validator * (len(validators) - 1)
        smt.set(balance_key(kp.address), _int_to_bytes(amount))
        smt.set(stake_key(kp.address), _int_to_bytes(amount))
        smt.set(nonce_key(kp.address), _int_to_bytes(0))

    leader_kp = validators[0]
    header = BlockHeader(
        slot=GENESIS_SLOT,
        parent_slot=-1,
        parent_hash=bytes(32),
        transactions_root=digest("empty_tx_root"),
        state_root=smt.root(),
        base_fee=BASE_FEE_INITIAL,
        leader=leader_kp.address,
        timestamp=GENESIS_TIME_MS,
    )
    return Block(header=header, transactions=[])


def initialize_ledger(validators: List[KeyPair]) -> Ledger:
    """Create and populate a fresh Tachyon Ledger with genesis block and stake."""
    ledger = Ledger()
    smt = SparseMerkleTree()
    genesis_block = create_genesis_block(validators, smt)
    ledger.add_block(genesis_block)

    # Set validator stakes
    total_stake = GENESIS_REWARD_POOL // len(validators)
    for kp in validators:
        ledger.set_stake(kp.address, total_stake)

    # Vote on genesis
    for kp in validators:
        ledger.add_vote(Vote(kp.address, GENESIS_SLOT, genesis_block.header.hash(), GENESIS_TIME_MS))

    return ledger
