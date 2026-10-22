"""Tachoin node: orchestrates Tachyon's chain for the TACH token.

The TachoinNode wraps a Tachyon Ledger and adds tachoin-specific execution:
  * Transfer TACH between addresses (with fee)
  * Mint TACH (validator authority only)
  * Burn TACH
  * Stake / Unstake TACH to validators
"""

from __future__ import annotations

import json
import sys
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Add Tachyon to path
_TACHYON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tachyon-blockchain")
if _TACHYON_PATH not in sys.path:
    sys.path.insert(0, _TACHYON_PATH)

from tachyon.chain import Ledger, Block, BlockHeader, Transaction, Vote, GENESIS_SLOT, GENESIS_TIME_MS, BASE_FEE_INITIAL, SLOT_MS
from tachyon.crypto import KeyPair
from tachyon.smt import SparseMerkleTree
from tachyon.mempool import Mempool
from tachyon.election import LeaderElection
from tachyon.encoding import digest, u64, canonical_json

from .config import (
    TOTAL_SUPPLY, GENESIS_REWARD_POOL,
    STATE_KEY_TOTAL_SUPPLY, STATE_KEY_CIRCULATING_SUPPLY, STATE_KEY_BURNED_SUPPLY,
    balance_key, stake_key, nonce_key,
    TRANSFER_FEE, TOKEN_DECIMALS,
)
from .wallet import TachoinWallet
from .transaction import TachoinTx, decode_instruction


@dataclass
class TachoinResult:
    """Result of applying a tachoin transaction."""
    success: bool
    tx_hash: str
    new_balance: int
    error: Optional[str] = None


def _int_to_bytes(value: int) -> bytes:
    """Encode an arbitrary non-negative integer to big-endian bytes.
    Uses length prefix so SMT can distinguish zero from empty."""
    if value == 0:
        return b"\x00"
    return value.to_bytes((value.bit_length() + 7) // 8, "big")


def _bytes_to_int(data: Optional[bytes]) -> int:
    if data is None or data == b"" or data == b"\x00":
        return 0
    return int.from_bytes(data, "big")


class TachoinNode:
    """Tachoin node managing the TACH token on top of Tachyon.

    Usage:
        validators = [KeyPair.generate() for _ in range(4)]
        node = TachoinNode(validators)

        # Or with a pre-built ledger:
        node = TachoinNode(validators, ledger=my_ledger)
    """

    def __init__(self, validators: List[KeyPair], ledger: Optional[Ledger] = None):
        self._validators = validators
        self._validator_addrs = [kp.address for kp in validators]
        self._validator_set = set(self._validator_addrs)

        # SMT for tachoin state (balances, stakes, nonces, supply)
        self.smt = SparseMerkleTree()

        # Build genesis state in our SMT
        self._build_genesis_state()

        # Create or reuse ledger
        if ledger is None:
            ledger = Ledger()
        self.ledger = ledger

        # Add genesis block to ledger
        genesis = self._create_genesis_block()
        self.ledger.add_block(genesis)

        # Set validator stakes for BFT quorum
        per_validator = GENESIS_REWARD_POOL // len(self._validators)
        for kp in self._validators:
            self.ledger.set_stake(kp.address, per_validator)

        # Vote on genesis
        for kp in self._validators:
            self.ledger.add_vote(Vote(kp.address, GENESIS_SLOT, genesis.header.hash(), GENESIS_TIME_MS))

        # Mempool for pending transactions
        self.mempool = Mempool()

        # Leader election (round-robin among validators)
        self.election = LeaderElection(self._validator_addrs)

        # Track current slot
        self._current_slot = self.ledger.current_slot
        self._last_block_hash = genesis.header.hash()

    def _build_genesis_state(self) -> None:
        """Populate the SMT with initial tachoin token state."""
        from .genesis import _int_to_bytes

        self.smt.set(STATE_KEY_TOTAL_SUPPLY, _int_to_bytes(TOTAL_SUPPLY))
        self.smt.set(STATE_KEY_CIRCULATING_SUPPLY, _int_to_bytes(GENESIS_REWARD_POOL))
        self.smt.set(STATE_KEY_BURNED_SUPPLY, _int_to_bytes(TOTAL_SUPPLY - GENESIS_REWARD_POOL))

        per_validator = GENESIS_REWARD_POOL // len(self._validators)
        for i, kp in enumerate(self._validators):
            amount = per_validator if i < len(self._validators) - 1 else GENESIS_REWARD_POOL - per_validator * (len(self._validators) - 1)
            self.smt.set(balance_key(kp.address), _int_to_bytes(amount))
            self.smt.set(stake_key(kp.address), _int_to_bytes(amount))
            self.smt.set(nonce_key(kp.address), _int_to_bytes(0))

    def _create_genesis_block(self) -> Block:
        """Create the genesis block using the node's SMT."""
        from .genesis import create_genesis_block
        return create_genesis_block(self._validators, self.smt)

    # ---------- State accessors ----------

    def get_balance(self, address: str) -> int:
        """Get TACH balance for an address (in least units)."""
        return _bytes_to_int(self.smt.get(balance_key(address)))

    def get_stake(self, address: str) -> int:
        """Get staked TACH for an address."""
        return _bytes_to_int(self.smt.get(stake_key(address)))

    def get_total_supply(self) -> int:
        return _bytes_to_int(self.smt.get(STATE_KEY_TOTAL_SUPPLY))

    def get_circulating_supply(self) -> int:
        return _bytes_to_int(self.smt.get(STATE_KEY_CIRCULATING_SUPPLY))

    def get_burned_supply(self) -> int:
        return _bytes_to_int(self.smt.get(STATE_KEY_BURNED_SUPPLY))

    def get_current_slot(self) -> int:
        return self._current_slot

    def get_latest_block_hash(self) -> str:
        return self._last_block_hash.hex()

    def format_tach(self, amount: int) -> str:
        """Format least units to a human-readable TACH string."""
        whole = amount // (10 ** TOKEN_DECIMALS)
        frac = (amount % (10 ** TOKEN_DECIMALS)) // (10 ** (TOKEN_DECIMALS - 6))
        return f"{whole}.{frac:06d} TACH"

    def parse_tach(self, amount_str: str) -> int:
        """Parse a human-readable TACH string to least units."""
        if "." in amount_str:
            whole, frac = amount_str.split(".")
            frac = (frac + "0" * 6)[:6]
            return int(whole) * (10 ** TOKEN_DECIMALS) + int(frac) * (10 ** (TOKEN_DECIMALS - 6))
        return int(amount_str) * (10 ** TOKEN_DECIMALS)

    # ---------- Transaction submission ----------

    def submit_transaction(self, tx: TachoinTx) -> TachoinResult:
        """Submit a signed TachoinTx to the mempool and attempt immediate execution."""
        if not tx.verify():
            return TachoinResult(success=False, tx_hash=tx.message_bytes()[:32].hex(), new_balance=0, error="Invalid signature")

        tachyon_tx = tx.to_tachyon_transaction()
        if not self.mempool.add(tachyon_tx):
            return TachoinResult(success=False, tx_hash=tachyon_tx.signature.hex(), new_balance=0, error="Transaction already in mempool or pool full")

        # Execute immediately for simulation
        result = self._execute_transaction(tx)
        return result

    def _execute_transaction(self, tx: TachoinTx) -> TachoinResult:
        """Execute a single tachoin transaction against SMT state."""
        program_id, payload = tx.instructions[0]
        data = decode_instruction(payload)

        if program_id == "tachoin_transfer":
            return self._do_transfer(tx, data)
        elif program_id == "tachoin_mint":
            return self._do_mint(tx, data)
        elif program_id == "tachoin_burn":
            return self._do_burn(tx, data)
        elif program_id == "tachoin_stake":
            return self._do_stake(tx, data)
        elif program_id == "tachoin_unstake":
            return self._do_unstake(tx, data)
        else:
            return TachoinResult(success=False, tx_hash="", new_balance=0, error=f"Unknown program: {program_id}")

    # ---------- State transitions ----------

    def _do_transfer(self, tx: TachoinTx, data: dict) -> TachoinResult:
        to_addr = data["to"]
        amount = int(data["amount"])
        fee = int(data.get("fee", TRANSFER_FEE))

        sender_balance = self.get_balance(tx.sender)
        total = amount + fee
        if sender_balance < total:
            return TachoinResult(False, tx.message_bytes()[:32].hex(), sender_balance, "Insufficient balance")

        # Deduct sender
        self.smt.set(balance_key(tx.sender), _int_to_bytes(sender_balance - total))
        # Credit receiver
        recv_balance = self.get_balance(to_addr)
        self.smt.set(balance_key(to_addr), _int_to_bytes(recv_balance + amount))
        # Fee goes to current block leader (simulated)
        leader = self.election.get_leader(self._current_slot)
        leader_balance = self.get_balance(leader)
        self.smt.set(balance_key(leader), _int_to_bytes(leader_balance + fee))

        tx_hash = digest("tachoin_tx", tx.message_bytes()).hex()
        return TachoinResult(True, tx_hash, self.get_balance(tx.sender))

    def _do_mint(self, tx: TachoinTx, data: dict) -> TachoinResult:
        if tx.sender not in self._validator_set:
            return TachoinResult(False, tx.message_bytes()[:32].hex(), 0, "Only validators can mint")

        amount = int(data["amount"])
        circulating = self.get_circulating_supply()
        total = self.get_total_supply()
        if circulating + amount > total:
            return TachoinResult(False, tx.message_bytes()[:32].hex(), 0, "Exceeds total supply cap")

        self.smt.set(STATE_KEY_CIRCULATING_SUPPLY, _int_to_bytes(circulating + amount))
        minted = self.get_balance(tx.sender)
        self.smt.set(balance_key(tx.sender), _int_to_bytes(minted + amount))

        tx_hash = digest("tachoin_tx", tx.message_bytes()).hex()
        return TachoinResult(True, tx_hash, self.get_balance(tx.sender))

    def _do_burn(self, tx: TachoinTx, data: dict) -> TachoinResult:
        amount = int(data["amount"])
        sender_balance = self.get_balance(tx.sender)
        if sender_balance < amount:
            return TachoinResult(False, tx.message_bytes()[:32].hex(), sender_balance, "Insufficient balance to burn")

        circulating = self.get_circulating_supply()
        burned = self.get_burned_supply()

        self.smt.set(balance_key(tx.sender), _int_to_bytes(sender_balance - amount))
        self.smt.set(STATE_KEY_CIRCULATING_SUPPLY, _int_to_bytes(circulating - amount))
        self.smt.set(STATE_KEY_BURNED_SUPPLY, _int_to_bytes(burned + amount))

        tx_hash = digest("tachoin_tx", tx.message_bytes()).hex()
        return TachoinResult(True, tx_hash, self.get_balance(tx.sender))

    def _do_stake(self, tx: TachoinTx, data: dict) -> TachoinResult:
        amount = int(data["amount"])
        validator_addr = data.get("validator", "")
        if validator_addr and validator_addr not in self._validator_set:
            return TachoinResult(False, tx.message_bytes()[:32].hex(), 0, "Unknown validator")

        sender_balance = self.get_balance(tx.sender)
        if sender_balance < amount:
            return TachoinResult(False, tx.message_bytes()[:32].hex(), sender_balance, "Insufficient balance to stake")

        # Move from balance to stake
        self.smt.set(balance_key(tx.sender), _int_to_bytes(sender_balance - amount))
        current_stake = self.get_stake(tx.sender)
        self.smt.set(stake_key(tx.sender), _int_to_bytes(current_stake + amount))

        # Also update ledger stake map for BFT quorum
        if validator_addr:
            self.ledger.set_stake(validator_addr, self.ledger.get_stake(validator_addr) + amount)

        tx_hash = digest("tachoin_tx", tx.message_bytes()).hex()
        return TachoinResult(True, tx_hash, self.get_balance(tx.sender))

    def _do_unstake(self, tx: TachoinTx, data: dict) -> TachoinResult:
        amount = int(data["amount"])
        current_stake = self.get_stake(tx.sender)
        if current_stake < amount:
            return TachoinResult(False, tx.message_bytes()[:32].hex(), 0, "Insufficient stake to unstake")

        self.smt.set(stake_key(tx.sender), _int_to_bytes(current_stake - amount))
        balance = self.get_balance(tx.sender)
        self.smt.set(balance_key(tx.sender), _int_to_bytes(balance + amount))

        tx_hash = digest("tachoin_tx", tx.message_bytes()).hex()
        return TachoinResult(True, tx_hash, self.get_balance(tx.sender))

    # ---------- Block production ----------

    def produce_block(self, txs: Optional[List[TachoinTx]] = None) -> Optional[Block]:
        """Produce the next block, optionally including given transactions."""
        self._current_slot += 1
        slot = self._current_slot
        leader_addr = self.election.get_leader(slot)

        # Execute transactions
        if txs is None:
            txs = []
        for tx in txs:
            self._execute_transaction(tx)

        # Build header
        parent_hash = self._last_block_hash
        header = BlockHeader(
            slot=slot,
            parent_slot=slot - 1,
            parent_hash=parent_hash,
            transactions_root=digest("tachoin_tx_root", *[digest("t", t.message_bytes()) for t in txs]) if txs else digest("empty_tx_root"),
            state_root=self.smt.root(),
            base_fee=BASE_FEE_INITIAL,
            leader=leader_addr,
            timestamp=GENESIS_TIME_MS + (slot * SLOT_MS),
        )
        tachyon_txs = [tx.to_tachyon_transaction() for tx in txs]
        block = Block(header=header, transactions=tachyon_txs)

        # Add to ledger
        self.ledger.add_block(block)

        # Validators vote
        for kp in self._validators:
            self.ledger.add_vote(Vote(kp.address, slot, header.hash(), header.timestamp))

        self._last_block_hash = header.hash()
        return block

    def produce_blocks(self, count: int, txs_per_block: int = 3) -> int:
        """Produce multiple blocks with random transfers for benchmarking."""
        for _ in range(count):
            txs = []
            for i in range(txs_per_block):
                sender = self._validators[(self._current_slot + i) % len(self._validators)]
                receiver = self._validators[(self._current_slot + i + 1) % len(self._validators)]
                amount = (1 + (self._current_slot * 7 + i) % 100) * (10 ** TOKEN_DECIMALS)
                tx = TachoinTx.build_transfer(self._make_wallet(sender.address), receiver.address, amount, self._current_slot)
                txs.append(tx)
            self.produce_block(txs)
        return self._current_slot

    # ---------- Helpers ----------

    def _make_wallet(self, address: str) -> TachoinWallet:
        """Create a TachoinWallet from a keypair address (for building txs in simulation)."""
        for kp in self._validators:
            if kp.address == address:
                return _keypair_to_wallet(kp)
        raise ValueError(f"Unknown address: {address}")

    def status(self) -> dict:
        """Return a status snapshot of the node."""
        return {
            "network": "tachoin",
            "token": "TACH",
            "current_slot": self._current_slot,
            "finalized_slot": self.ledger.finalized_slot,
            "total_blocks": len(self.ledger.blocks),
            "mempool_size": self.mempool.size(),
            "total_supply": self.format_tach(self.get_total_supply()),
            "circulating_supply": self.format_tach(self.get_circulating_supply()),
            "burned_supply": self.format_tach(self.get_burned_supply()),
            "latest_block_hash": self.get_latest_block_hash(),
            "validators": len(self._validator_addrs),
            "state_root": self.smt.root().hex()[:16],
        }


def _keypair_to_wallet(kp: KeyPair) -> TachoinWallet:
    """Convert a Tachyon KeyPair to a TachoinWallet."""
    return TachoinWallet(seed=kp.seed)
