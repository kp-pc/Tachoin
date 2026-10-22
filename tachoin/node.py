"""The Tachoin reference node: token state machine over a Tachyon ledger.

Design notes
------------
* TACH balances, stakes and nonces live in a :class:`~tachoin.state.TokenState`,
  which owns the values and mirrors them into a Tachyon sparse Merkle tree for
  the state root committed in block headers.
* A transaction is validated and applied exactly once, at
  :meth:`TachoinNode.submit_transaction`.  Accepted transactions are queued and
  the next produced block includes them *without* re-applying them, so a block
  is a record of work already done.
* Every account is identified by its ``tach``-prefixed tachoin address; the
  underlying ``tch``-prefixed Tachyon address is never used as a state key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from ._tachyon import ensure_tachyon

ensure_tachyon()

from tachyon.chain import (
    BASE_FEE_INITIAL,
    GENESIS_SLOT,
    GENESIS_TIME_MS,
    SLOT_MS,
    Block,
    BlockHeader,
    Ledger,
    Vote,
)
from tachyon.crypto import KeyPair
from tachyon.election import LeaderElection
from tachyon.encoding import digest

from .config import (
    DISPLAY_DECIMALS,
    MAX_PENDING_TXS,
    SLOT_FRESHNESS_SLOTS,
    STATE_KEY_BURNED_SUPPLY,
    STATE_KEY_CIRCULATING_SUPPLY,
    STATE_KEY_TOTAL_SUPPLY,
    STATE_KEY_UNCIRCULATED_SUPPLY,
    TOKEN_DECIMALS,
    TRANSFER_FEE,
    balance_key,
    delegation_key,
    nonce_key,
    stake_key,
    validator_stake_key,
)
from .genesis import (
    apply_genesis_state,
    bytes_to_int,
    create_genesis_block,
    int_to_bytes,
    validator_addresses,
)
from .state import TokenState
from .transaction import (
    PROGRAM_BURN,
    PROGRAM_MINT,
    PROGRAM_STAKE,
    PROGRAM_TRANSFER,
    PROGRAM_UNSTAKE,
    TachoinTx,
    TransactionError,
)
from .wallet import TachoinWallet


# ---- Amount formatting -------------------------------------------------


def format_tach(amount: int) -> str:
    """Format base units as ``"<whole>.<fraction> TACH"``."""
    if not isinstance(amount, int) or isinstance(amount, bool):
        raise TypeError("amount must be an integer number of base units")
    sign = "-" if amount < 0 else ""
    value = abs(amount)
    scale = 10 ** (TOKEN_DECIMALS - DISPLAY_DECIMALS)
    whole, remainder = divmod(value, 10 ** TOKEN_DECIMALS)
    fraction = remainder // scale
    return f"{sign}{whole}.{fraction:0{DISPLAY_DECIMALS}d} TACH"


def parse_tach(text: str) -> int:
    """Parse ``"12.5"``, ``"12.5 TACH"`` or ``"12.5 tach"`` into base units."""
    if not isinstance(text, str):
        raise ValueError("amount must be a string")
    cleaned = text.strip().replace("_", "")
    if cleaned.lower().endswith("tach"):
        cleaned = cleaned[: -len("tach")].strip()
    if not cleaned:
        raise ValueError("amount is empty")
    if cleaned.startswith("-"):
        raise ValueError("amount cannot be negative")

    whole_text, _, fraction_text = cleaned.partition(".")
    whole_text = whole_text or "0"
    if not whole_text.isdigit():
        raise ValueError(f"invalid amount: {text!r}")
    if fraction_text and not fraction_text.isdigit():
        raise ValueError(f"invalid amount: {text!r}")
    if len(fraction_text) > TOKEN_DECIMALS:
        raise ValueError(f"amount has more than {TOKEN_DECIMALS} decimal places")

    fraction_text = fraction_text.ljust(TOKEN_DECIMALS, "0")
    return int(whole_text) * (10 ** TOKEN_DECIMALS) + int(fraction_text)


@dataclass(frozen=True)
class TachoinResult:
    """Outcome of submitting a transaction."""

    success: bool
    program: str
    tx_hash: str
    sender: str
    nonce: int
    new_balance: int
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "program": self.program,
            "tx_hash": self.tx_hash,
            "sender": self.sender,
            "nonce": self.nonce,
            "new_balance": self.new_balance,
            "new_balance_tach": format_tach(self.new_balance),
            "error": self.error,
        }


class TachoinNode:
    """Reference implementation of the Tachoin token state machine."""

    def __init__(
        self,
        validators: Sequence[KeyPair],
        genesis_timestamp: int = GENESIS_TIME_MS,
    ):
        if not validators:
            raise ValueError("at least one validator is required")
        self._validators: List[KeyPair] = list(validators)
        self._validator_addrs: List[str] = validator_addresses(self._validators)
        self._validator_set: Set[str] = set(self._validator_addrs)
        self._genesis_timestamp = genesis_timestamp

        self.state = TokenState()
        self._allocations = apply_genesis_state(self.state, self._validators)

        self._known_addresses: Set[str] = {address for address, _ in self._allocations}

        self.ledger = Ledger()
        self._genesis = self._build_genesis()
        self.ledger.add_block(self._genesis)

        # Write genesis stakes into both the SMT (validator_stake_key) and the
        # ledger so that the first produce_block sync from the SMT does not
        # overwrite the election weight with zero.
        for address, stake in self._allocations:
            self.state.set(
                validator_stake_key(address), int_to_bytes(stake)
            )
            self.ledger.set_stake(address, stake)
        for address in self._validator_addrs:
            self.ledger.add_vote(
                Vote(
                    address,
                    GENESIS_SLOT,
                    self._genesis.header.hash(),
                    self._genesis_timestamp,
                )
            )

        self.election = LeaderElection(self._validator_addrs)
        self._pending: List[TachoinTx] = []
        self._current_slot = GENESIS_SLOT
        self._last_block_hash = self._genesis.header.hash()

    def _build_genesis(self) -> Block:
        block = create_genesis_block(self._validators, self.state)
        return block

    # ---- Balance / supply reads ---------------------------------------

    def get_balance(self, address: str) -> int:
        return bytes_to_int(self.state.get(balance_key(address)))

    def get_stake(self, address: str) -> int:
        """Return the total TACH ``address`` has personally staked."""
        return bytes_to_int(self.state.get(stake_key(address)))

    def get_validator_stake(self, address: str) -> int:
        """Return the total TACH delegated to ``address`` (election weight)."""
        return bytes_to_int(self.state.get(validator_stake_key(address)))

    def get_nonce(self, address: str) -> int:
        """Next nonce expected from ``address``."""
        return bytes_to_int(self.state.get(nonce_key(address)))

    def get_total_supply(self) -> int:
        return bytes_to_int(self.state.get(STATE_KEY_TOTAL_SUPPLY))

    def get_circulating_supply(self) -> int:
        return bytes_to_int(self.state.get(STATE_KEY_CIRCULATING_SUPPLY))

    def get_uncirculated_supply(self) -> int:
        return bytes_to_int(self.state.get(STATE_KEY_UNCIRCULATED_SUPPLY))

    def get_burned_supply(self) -> int:
        return bytes_to_int(self.state.get(STATE_KEY_BURNED_SUPPLY))

    def supply(self) -> Dict[str, str]:
        return {
            "total": format_tach(self.get_total_supply()),
            "circulating": format_tach(self.get_circulating_supply()),
            "uncirculated": format_tach(self.get_uncirculated_supply()),
            "burned": format_tach(self.get_burned_supply()),
        }

    def accounts(self) -> List[Tuple[str, int]]:
        """Every address this node has ever credited or debited."""
        return [(address, self.get_balance(address)) for address in sorted(self._known_addresses)]

    def balances_sum(self) -> int:
        """Sum of tracked spendable balances."""
        return sum(balance for _, balance in self.accounts())

    def stakes_sum(self) -> int:
        """Sum of tracked staked amounts."""
        return sum(self.get_stake(address) for address in self._known_addresses)

    def check_supply_invariant(self) -> bool:
        """True when circulating + uncirculated + burned equals the total."""
        return (
            self.get_circulating_supply()
            + self.get_uncirculated_supply()
            + self.get_burned_supply()
            == self.get_total_supply()
        )

    def check_balance_invariant(self) -> bool:
        """True when stake and balances together account for every circulating unit.

        Staked TACH leaves the spendable balance key but remains circulating, so
        conservation is ``balances + stakes == circulating``.
        """
        return self.balances_sum() + self.stakes_sum() == self.get_circulating_supply()

    # ---- Identity ------------------------------------------------------

    def is_validator(self, address: str) -> bool:
        return address in self._validator_set

    def validator_addresses(self) -> List[str]:
        return list(self._validator_addrs)

    def wallet_for(self, address: str) -> TachoinWallet:
        """Return the validator wallet for ``address`` (simulation helper)."""
        for kp in self._validators:
            wallet = TachoinWallet(seed=kp.seed)
            if wallet.address == address:
                return wallet
        raise ValueError(f"not a validator address: {address}")

    def get_current_slot(self) -> int:
        return self._current_slot

    def get_latest_block_hash(self) -> str:
        return self._last_block_hash.hex()

    def pending_transactions(self) -> List[TachoinTx]:
        return list(self._pending)

    def status(self) -> Dict[str, Any]:
        return {
            "network": "tachoin",
            "token": "TACH",
            "current_slot": self._current_slot,
            "finalized_slot": self.ledger.finalized_slot,
            "total_blocks": len(self.ledger.blocks),
            "pending_transactions": len(self._pending),
            "total_supply": format_tach(self.get_total_supply()),
            "circulating_supply": format_tach(self.get_circulating_supply()),
            "uncirculated_supply": format_tach(self.get_uncirculated_supply()),
            "burned_supply": format_tach(self.get_burned_supply()),
            "supply_invariant_ok": self.check_supply_invariant(),
            "latest_block_hash": self.get_latest_block_hash(),
            "validators": len(self._validator_addrs),
            "state_root": self.state.root().hex(),
        }

    # ---- Submission ----------------------------------------------------

    def _result(
        self, tx: TachoinTx, success: bool, error: Optional[str] = None
    ) -> TachoinResult:
        return TachoinResult(
            success=success,
            program=tx.program,
            tx_hash=tx.tx_hash(),
            sender=tx.sender,
            nonce=tx.nonce,
            new_balance=self.get_balance(tx.sender),
            error=error,
        )

    def submit_transaction(self, tx: TachoinTx) -> TachoinResult:
        """Validate and apply ``tx`` exactly once, queueing it for the next block."""
        if not isinstance(tx, TachoinTx):
            raise TypeError("expected a TachoinTx")
        if not tx.verify():
            return self._result(tx, False, "invalid signature")

        # Slot freshness: enforce both upper and lower bounds so a
        # transaction cannot be replayed from a slot more than
        # SLOT_FRESHNESS_SLOTS ago and cannot be front-run by jumping
        # far ahead into the future.  The lower-bound check is critical
        # because it also closes the fee-evasion vector where a client
        # submits a transaction at a stale slot whose base fee is lower
        # than the current one.
        if tx.slot < self._current_slot - SLOT_FRESHNESS_SLOTS:
            return self._result(
                tx,
                False,
                f"slot {tx.slot} is too old "
                f"(current={self._current_slot}, min={self._current_slot - SLOT_FRESHNESS_SLOTS})",
            )
        if tx.slot > self._current_slot + SLOT_FRESHNESS_SLOTS:
            return self._result(
                tx,
                False,
                f"slot {tx.slot} exceeds freshness window "
                f"(current={self._current_slot}, max={self._current_slot + SLOT_FRESHNESS_SLOTS})",
            )

        # Nonce validation (replay protection)
        expected = self.get_nonce(tx.sender)
        if tx.nonce != expected:
            return self._result(
                tx,
                False,
                f"nonce {tx.nonce} does not match expected {expected} (replay attack or stale transaction)",
            )

        # Mempool bound: reject new work when the pending queue is full so a
        # flood cannot exhaust node memory before the next block drains it.
        if len(self._pending) >= MAX_PENDING_TXS:
            return self._result(tx, False, "mempool is full")

        handler = {
            PROGRAM_TRANSFER: self._apply_transfer,
            PROGRAM_MINT: self._apply_mint,
            PROGRAM_BURN: self._apply_burn,
            PROGRAM_STAKE: self._apply_stake,
            PROGRAM_UNSTAKE: self._apply_unstake,
        }[tx.program]

        snapshot = self.state.snapshot()
        try:
            error = handler(tx)
        except TransactionError as exc:
            self.state.restore(snapshot)
            return self._result(tx, False, str(exc))
        if error:
            self.state.restore(snapshot)
            return self._result(tx, False, error)

        self._known_addresses.add(tx.sender)
        self.state.set(nonce_key(tx.sender), int_to_bytes(expected + 1))
        self._pending.append(tx)
        return self._result(tx, True)

    # ---- Program handlers ---------------------------------------------

    def _credit(self, address: str, amount: int) -> None:
        """Add ``amount`` (which may be negative) to ``address``'s balance."""
        new_balance = self.get_balance(address) + amount
        if new_balance < 0:
            raise TransactionError("balance would become negative")
        self._known_addresses.add(address)
        self.state.set(balance_key(address), int_to_bytes(new_balance))

    def _apply_transfer(self, tx: TachoinTx) -> Optional[str]:
        data = tx.data()
        recipient = data["to"]
        amount = int(data["amount"])
        fee = int(data.get("fee", TRANSFER_FEE))
        if amount <= 0:
            return "transfer amount must be positive"
        if tx.sender == recipient:
            return "cannot transfer to self"
        # Enforce the mandatory fee: any transfer with fee < TRANSFER_FEE is
        # rejected.  This plugs the fee-bypass vector where a transaction
        # crafted with fee=0 would skip the validator payout entirely.
        if fee < TRANSFER_FEE:
            return f"fee must be at least {TRANSFER_FEE}, got {fee}"
        if self.get_balance(tx.sender) < amount + fee:
            return "insufficient balance"

        # The fee recipient is derived from the transaction's own signed slot, so
        # routing is deterministic and verifiable from the transaction alone
        # rather than depending on when the node happens to apply it.
        leader = self.election.get_leader(tx.slot)
        self._credit(tx.sender, -(amount + fee))
        self._credit(recipient, amount)
        self._credit(leader, fee)
        return None

    def _apply_mint(self, tx: TachoinTx) -> Optional[str]:
        if not self.is_validator(tx.sender):
            return "only validators may mint"
        amount = int(tx.data()["amount"])
        if amount <= 0:
            return "mint amount must be positive"
        uncirculated = self.get_uncirculated_supply()
        if amount > uncirculated:
            return "mint exceeds uncirculated supply"

        self._credit(tx.sender, amount)
        self.state.set(
            STATE_KEY_UNCIRCULATED_SUPPLY, int_to_bytes(uncirculated - amount)
        )
        self.state.set(
            STATE_KEY_CIRCULATING_SUPPLY,
            int_to_bytes(self.get_circulating_supply() + amount),
        )
        return None

    def _apply_burn(self, tx: TachoinTx) -> Optional[str]:
        amount = int(tx.data()["amount"])
        if amount <= 0:
            return "burn amount must be positive"
        if self.get_balance(tx.sender) < amount:
            return "insufficient balance to burn"

        self._credit(tx.sender, -amount)
        self.state.set(
            STATE_KEY_CIRCULATING_SUPPLY,
            int_to_bytes(self.get_circulating_supply() - amount),
        )
        self.state.set(
            STATE_KEY_BURNED_SUPPLY, int_to_bytes(self.get_burned_supply() + amount)
        )
        return None

    def _apply_stake(self, tx: TachoinTx) -> Optional[str]:
        """Apply a stake transaction.

        The SMT is the single source of truth for token stake.  The Tachyon
        ledger is synced from the SMT at block-production time (see
        :meth:`produce_block`), so a rejected block cannot leave the two
        stores out of step.
        """
        data = tx.data()
        amount = int(data["amount"])
        validator = data.get("validator") or tx.sender
        if amount <= 0:
            return "stake amount must be positive"
        if not self.is_validator(validator):
            return "unknown validator"
        if self.get_balance(tx.sender) < amount:
            return "insufficient balance to stake"

        self._credit(tx.sender, -amount)
        self.state.set(
            stake_key(tx.sender), int_to_bytes(self.get_stake(tx.sender) + amount)
        )
        # Track the delegation in the validator's election-weight bucket so the
        # SMT remains the source of truth for both personal stake and election
        # weight, preventing ledger/SMT drift.
        self.state.set(
            validator_stake_key(validator),
            int_to_bytes(self.get_validator_stake(validator) + amount),
        )
        # Record explicit delegation for validation during unstake.
        self.state.set(
            delegation_key(tx.sender, validator),
            int_to_bytes(
                bytes_to_int(self.state.get(delegation_key(tx.sender, validator), b"\x00"))
                + amount,
            ),
        )
        # Ledger sync deferred to produce_block to keep SMT and ledger in lock-step.
        return None

    def _apply_unstake(self, tx: TachoinTx) -> Optional[str]:
        """Apply an unstake transaction.

        Same principle as :meth:`_apply_stake`: the SMT is authoritative,
        and the ledger is reconciled at block-production time.
        """
        data = tx.data()
        amount = int(data["amount"])
        validator = data.get("validator") or tx.sender
        if amount <= 0:
            return "unstake amount must be positive"
        
        # Check personal stake sufficiency (as before)
        staked = self.get_stake(tx.sender)
        if staked < amount:
            return "insufficient stake to unstake"
        
        # NEW: Verify the delegator has staked with this specific validator.
        # Read the delegation record for (delegator, validator) pair.
        delegation_key_bytes = delegation_key(tx.sender, validator)
        current_delegation = bytes_to_int(self.state.get(delegation_key_bytes, b"\x00"))
        if current_delegation < amount:
            return "insufficient delegation to this validator"

        self._credit(tx.sender, amount)
        self.state.set(stake_key(tx.sender), int_to_bytes(staked - amount))
        # Decrement the validator's election-weight bucket alongside the personal
        # stake bucket so both SMT views stay in sync.
        self.state.set(
            validator_stake_key(validator),
            int_to_bytes(
                max(0, self.get_validator_stake(validator) - amount)
            ),
        )
        # Update the delegation ledger to reflect the reduced delegation.
        self.state.set(
            delegation_key_bytes,
            int_to_bytes(max(0, current_delegation - amount)),
        )
        # Ledger sync deferred to produce_block to keep SMT and ledger in lock-step.
        return None

    # ---- Block production ---------------------------------------------

    def produce_block(self) -> Block:
        """Produce the next block from queued, already-applied transactions."""
        included: List[TachoinTx] = list(self._pending)
        self._pending.clear()

        self._current_slot += 1
        slot = self._current_slot
        header = BlockHeader(
            slot=slot,
            parent_slot=slot - 1,
            parent_hash=self._last_block_hash,
            transactions_root=(
                digest(
                    "tachoin_tx_root",
                    *[digest("tx", tx.message_bytes()) for tx in included],
                )
                if included
                else digest("empty_tx_root")
            ),
            state_root=self.state.root(),
            base_fee=BASE_FEE_INITIAL,
            leader=self.election.get_leader(slot),
            timestamp=self._genesis_timestamp + slot * SLOT_MS,
        )
        # Sync validator stakes from the SMT into the ledger so that the
        # election and finalisation logic sees the same stake weights the
        # token state records.  Deferring this to block-production time means
        # a rejected block cannot leave the two stores out of step.
        for validator in self._validator_addrs:
            self.ledger.set_stake(validator, self.get_validator_stake(validator))

        block = Block(
            header=header,
            transactions=[tx.to_tachyon_transaction() for tx in included],
        )
        if not self.ledger.add_block(block):
            raise RuntimeError(f"ledger rejected block at slot {slot}")

        for address in self._validator_addrs:
            self.ledger.add_vote(
                Vote(address, slot, header.hash(), header.timestamp)
            )
        self._last_block_hash = header.hash()
        return block

    def produce_blocks(
        self, count: int, transactions_per_block: int = 0
    ) -> List[Block]:
        """Produce ``count`` blocks, optionally submitting small transfers first."""
        if count < 1:
            raise ValueError("count must be at least 1")
        wallets = [TachoinWallet(seed=kp.seed) for kp in self._validators]
        blocks: List[Block] = []
        for _ in range(count):
            for index in range(transactions_per_block):
                sender = wallets[(self._current_slot + index) % len(wallets)]
                recipient = wallets[(self._current_slot + index + 1) % len(wallets)]
                amount = 10 ** TOKEN_DECIMALS
                if self.get_balance(sender.address) < amount + TRANSFER_FEE:
                    continue
                self.submit_transaction(
                    TachoinTx.build_transfer(
                        sender,
                        recipient.address,
                        amount,
                        self.get_nonce(sender.address),
                        self._current_slot + 1,
                    )
                )
            blocks.append(self.produce_block())
        return blocks
