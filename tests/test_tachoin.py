"""Regression suite for Tachoin.

Run with the standard library only::

    python -m unittest discover -s tests -v

Tachoin resolves its Tachyon dependency itself (see ``tachoin._tachyon``), so
these tests work from a plain checkout with ``tachyon-blockchain`` beside it,
or with ``TACHYON_PATH`` set.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import tachoin  # noqa: E402  (resolves the Tachyon dependency)
from tachyon.crypto import KeyPair  # noqa: E402

from tachoin.config import (  # noqa: E402
    GENESIS_REWARD_POOL,
    TOTAL_SUPPLY,
    TOKEN_DECIMALS,
    TRANSFER_FEE,
    UNCIRCULATED_SUPPLY,
)
from tachoin.node import TachoinNode, format_tach, parse_tach  # noqa: E402
from tachoin.transaction import (  # noqa: E402
    TachoinTx,
    TransactionError,
    encode_transfer,
)
from tachoin.wallet import TachoinWallet, is_valid_address  # noqa: E402

ONE_TACH = 10 ** TOKEN_DECIMALS


def make_node(count: int = 4):
    """Return (node, wallets) for a deterministic validator set."""
    keypairs = [KeyPair.from_seed(bytes([i + 1]) * 32) for i in range(count)]
    node = TachoinNode(keypairs)
    wallets = [TachoinWallet(seed=kp.seed) for kp in keypairs]
    return node, wallets


class WalletTests(unittest.TestCase):
    def test_generated_address_is_prefixed_and_valid(self):
        wallet = TachoinWallet.generate()
        self.assertTrue(wallet.address.startswith("tach"))
        self.assertTrue(is_valid_address(wallet.address))

    def test_seed_roundtrip_is_deterministic(self):
        wallet = TachoinWallet.generate()
        restored = TachoinWallet.from_seed_hex(wallet.seed_hex)
        self.assertEqual(wallet.address, restored.address)

    def test_address_is_not_the_tachyon_address(self):
        """Balances must key off tachoin addresses, not tachyon 'tch' ones."""
        keypair = KeyPair.generate()
        wallet = TachoinWallet(seed=keypair.seed)
        self.assertTrue(keypair.address.startswith("tch"))
        self.assertNotEqual(keypair.address, wallet.address)

    def test_invalid_addresses_rejected(self):
        for candidate in ("", "tach", "tch5abc", "tach!!!!", None, 42):
            self.assertFalse(is_valid_address(candidate), candidate)

    def test_signature_verification(self):
        wallet = TachoinWallet.generate()
        message = b"transfer 1 TACH"
        signature = wallet.sign(message)
        self.assertTrue(TachoinWallet.verify(wallet.address, message, signature))
        self.assertFalse(TachoinWallet.verify(wallet.address, b"other", signature))

    def test_signature_from_wrong_address_rejected(self):
        signer = TachoinWallet.generate()
        other = TachoinWallet.generate()
        message = b"payload"
        self.assertFalse(
            TachoinWallet.verify(other.address, message, signer.sign(message))
        )

    def test_mnemonic_is_normalised_and_stable(self):
        first = TachoinWallet.from_mnemonic("alpha beta gamma")
        second = TachoinWallet.from_mnemonic("  ALPHA   beta Gamma ")
        self.assertEqual(first.address, second.address)

    def test_empty_mnemonic_rejected(self):
        with self.assertRaises(ValueError):
            TachoinWallet.from_mnemonic("   ")


class WalletFileTests(unittest.TestCase):
    def setUp(self):
        self.wallet = TachoinWallet.generate()
        self.dir = tempfile.mkdtemp()
        self.passphrase = "correct horse battery staple"

    def path(self, name: str) -> str:
        return os.path.join(self.dir, name)

    def test_sealed_roundtrip(self):
        path = self.wallet.save(self.path("w.json"), self.passphrase)
        loaded = TachoinWallet.load(path, self.passphrase)
        self.assertEqual(self.wallet.address, loaded.address)

    def test_sealed_file_does_not_contain_plaintext_seed(self):
        path = self.wallet.save(self.path("w.json"), self.passphrase)
        with open(path, encoding="utf-8") as handle:
            self.assertNotIn(self.wallet.seed_hex, handle.read())

    def test_wrong_passphrase_rejected(self):
        path = self.wallet.save(self.path("w.json"), self.passphrase)
        with self.assertRaises(ValueError):
            TachoinWallet.load(path, "wrong passphrase")

    def test_missing_passphrase_rejected(self):
        path = self.wallet.save(self.path("w.json"), self.passphrase)
        with self.assertRaises(ValueError):
            TachoinWallet.load(path)

    def test_tampered_ciphertext_rejected(self):
        path = self.wallet.save(self.path("w.json"), self.passphrase)
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        ciphertext = payload["seed"]["ciphertext"]
        payload["seed"]["ciphertext"] = ciphertext[:-2] + (
            "00" if ciphertext[-2:] != "00" else "11"
        )
        tampered = self.path("tampered.json")
        with open(tampered, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        with self.assertRaises(ValueError):
            TachoinWallet.load(tampered, self.passphrase)

    def test_unsealed_roundtrip_is_marked(self):
        path = self.wallet.save(self.path("plain.json"))
        with open(path, encoding="utf-8") as handle:
            self.assertFalse(json.load(handle)["sealed"])
        self.assertEqual(self.wallet.address, TachoinWallet.load(path).address)


class AmountTests(unittest.TestCase):
    def test_parse_whole_and_fractional(self):
        self.assertEqual(parse_tach("1"), ONE_TACH)
        self.assertEqual(parse_tach("12.5"), 125 * ONE_TACH // 10)
        self.assertEqual(parse_tach("0.000000000000000001"), 1)

    def test_parse_accepts_symbol_suffix(self):
        self.assertEqual(parse_tach("3 TACH"), 3 * ONE_TACH)
        self.assertEqual(parse_tach("3 tach"), 3 * ONE_TACH)

    def test_parse_rejects_bad_input(self):
        for text in ("", "-1", "abc", "1.2.3", "1,000", "1." + "0" * 19):
            with self.assertRaises(ValueError, msg=text):
                parse_tach(text)

    def test_format_roundtrip(self):
        self.assertEqual(format_tach(parse_tach("12.5")), "12.500000 TACH")
        self.assertEqual(format_tach(0), "0.000000 TACH")

    def test_format_rejects_non_integer(self):
        with self.assertRaises(TypeError):
            format_tach("1.0")


class GenesisTests(unittest.TestCase):
    def test_supply_buckets_sum_to_total(self):
        node, _ = make_node()
        self.assertEqual(node.get_total_supply(), TOTAL_SUPPLY)
        self.assertEqual(node.get_circulating_supply(), GENESIS_REWARD_POOL)
        self.assertEqual(node.get_uncirculated_supply(), UNCIRCULATED_SUPPLY)
        self.assertEqual(node.get_burned_supply(), 0)
        self.assertTrue(node.check_supply_invariant())

    def test_genesis_balances_are_not_double_counted_as_stake(self):
        """A regression: writing allocations to both buckets inflated supply."""
        node, _ = make_node()
        self.assertEqual(node.stakes_sum(), 0)
        self.assertEqual(node.balances_sum(), node.get_circulating_supply())
        self.assertTrue(node.check_balance_invariant())

    def test_allocations_split_the_pool(self):
        node, wallets = make_node(3)
        balances = [node.get_balance(w.address) for w in wallets]
        self.assertEqual(sum(balances), GENESIS_REWARD_POOL)
        self.assertTrue(all(balance > 0 for balance in balances))

    def test_validators_are_tachoin_addresses(self):
        node, wallets = make_node()
        self.assertEqual(node.validator_addresses(), [w.address for w in wallets])

    def test_empty_validator_set_rejected(self):
        with self.assertRaises(ValueError):
            TachoinNode([])


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.node, self.wallets = make_node()

    def transfer(self, sender_index, to, amount, nonce=None, fee=TRANSFER_FEE):
        sender = self.wallets[sender_index]
        if nonce is None:
            nonce = self.node.get_nonce(sender.address)
        return self.node.submit_transaction(
            TachoinTx.build_transfer(
                sender, to, amount, nonce, self.node.get_current_slot() + 1, fee
            )
        )

    def test_transfer_moves_funds_and_charges_fee(self):
        before_sender = self.node.get_balance(self.wallets[0].address)
        before_recipient = self.node.get_balance(self.wallets[1].address)
        amount = 10 * ONE_TACH

        result = self.transfer(0, self.wallets[1].address, amount)
        self.assertTrue(result.success, result.error)
        self.assertEqual(
            self.node.get_balance(self.wallets[0].address),
            before_sender - amount - TRANSFER_FEE,
        )
        self.assertEqual(
            self.node.get_balance(self.wallets[1].address), before_recipient + amount
        )

    def test_transfer_preserves_conservation(self):
        self.transfer(0, self.wallets[1].address, 5 * ONE_TACH)
        self.assertTrue(self.node.check_supply_invariant())
        self.assertTrue(self.node.check_balance_invariant())

    def test_replayed_transaction_is_rejected(self):
        sender = self.wallets[0]
        tx = TachoinTx.build_transfer(
            sender, self.wallets[1].address, ONE_TACH, 0, 1
        )
        self.assertTrue(self.node.submit_transaction(tx).success)
        replay = self.node.submit_transaction(tx)
        self.assertFalse(replay.success)
        self.assertIn("invalid nonce", replay.error)

    def test_out_of_order_nonce_rejected(self):
        result = self.transfer(0, self.wallets[1].address, ONE_TACH, nonce=5)
        self.assertFalse(result.success)
        self.assertIn("invalid nonce", result.error)

    def test_nonce_advances_once_per_accepted_transaction(self):
        sender = self.wallets[0]
        self.assertEqual(self.node.get_nonce(sender.address), 0)
        self.transfer(0, self.wallets[1].address, ONE_TACH)
        self.assertEqual(self.node.get_nonce(sender.address), 1)
        self.transfer(0, self.wallets[1].address, ONE_TACH)
        self.assertEqual(self.node.get_nonce(sender.address), 2)

    def test_self_transfer_rejected(self):
        result = self.transfer(0, self.wallets[0].address, ONE_TACH)
        self.assertFalse(result.success)
        self.assertIn("self", result.error)

    def test_insufficient_balance_rejected(self):
        result = self.transfer(0, self.wallets[1].address, GENESIS_REWARD_POOL)
        self.assertFalse(result.success)
        self.assertIn("insufficient", result.error)

    def test_failed_transfer_does_not_consume_nonce(self):
        sender = self.wallets[0]
        self.transfer(0, self.wallets[1].address, GENESIS_REWARD_POOL)
        self.assertEqual(self.node.get_nonce(sender.address), 0)

    def test_failed_transfer_does_not_mutate_balances(self):
        before = self.node.get_balance(self.wallets[0].address)
        self.transfer(0, self.wallets[1].address, GENESIS_REWARD_POOL + 1)
        self.assertEqual(self.node.get_balance(self.wallets[0].address), before)

    def test_tampered_signature_rejected(self):
        sender = self.wallets[0]
        tx = TachoinTx.build_transfer(sender, self.wallets[1].address, ONE_TACH, 0, 1)
        forged = TachoinTx(
            sender=tx.sender,
            nonce=tx.nonce,
            program=tx.program,
            payload=tx.payload,
            slot=tx.slot,
            signature=bytes(64),
        )
        result = self.node.submit_transaction(forged)
        self.assertFalse(result.success)
        self.assertIn("signature", result.error)

    def test_invalid_recipient_rejected_at_build_time(self):
        with self.assertRaises(TransactionError):
            encode_transfer("tch5notatachoinaddress", ONE_TACH)


class SupplyTests(unittest.TestCase):
    def setUp(self):
        self.node, self.wallets = make_node()

    def test_mint_moves_uncirculated_into_circulating(self):
        sender = self.wallets[0]
        amount = 1000 * ONE_TACH
        before = self.node.get_uncirculated_supply()
        result = self.node.submit_transaction(
            TachoinTx.build_mint(sender, amount, 0, 1)
        )
        self.assertTrue(result.success, result.error)
        self.assertEqual(self.node.get_uncirculated_supply(), before - amount)
        self.assertTrue(self.node.check_supply_invariant())
        self.assertTrue(self.node.check_balance_invariant())

    def test_non_validator_cannot_mint(self):
        outsider = TachoinWallet.generate()
        tx = TachoinTx.build_mint(outsider, ONE_TACH, 0, 1)
        result = self.node.submit_transaction(tx)
        self.assertFalse(result.success)
        self.assertIn("validator", result.error)

    def test_mint_cannot_exceed_uncirculated_supply(self):
        sender = self.wallets[0]
        result = self.node.submit_transaction(
            TachoinTx.build_mint(sender, UNCIRCULATED_SUPPLY + 1, 0, 1)
        )
        self.assertFalse(result.success)
        self.assertIn("uncirculated", result.error)

    def test_burn_reduces_circulating_and_grows_burned(self):
        sender = self.wallets[0]
        amount = 50 * ONE_TACH
        circulating = self.node.get_circulating_supply()
        result = self.node.submit_transaction(
            TachoinTx.build_burn(sender, amount, 0, 1)
        )
        self.assertTrue(result.success, result.error)
        self.assertEqual(self.node.get_circulating_supply(), circulating - amount)
        self.assertEqual(self.node.get_burned_supply(), amount)
        self.assertTrue(self.node.check_supply_invariant())

    def test_burn_more_than_balance_rejected(self):
        sender = self.wallets[0]
        result = self.node.submit_transaction(
            TachoinTx.build_burn(sender, GENESIS_REWARD_POOL, 0, 1)
        )
        self.assertFalse(result.success)

    def test_supply_is_conserved_across_all_programs(self):
        w = self.wallets
        operations = [
            TachoinTx.build_transfer(w[0], w[1].address, 5 * ONE_TACH, 0, 1),
            TachoinTx.build_mint(w[0], 10 * ONE_TACH, 1, 1),
            TachoinTx.build_burn(w[0], 3 * ONE_TACH, 2, 1),
            TachoinTx.build_stake(w[0], 4 * ONE_TACH, w[1].address, 3, 1),
            TachoinTx.build_unstake(w[0], 2 * ONE_TACH, w[1].address, 4, 1),
        ]
        for tx in operations:
            result = self.node.submit_transaction(tx)
            self.assertTrue(result.success, f"{tx.program}: {result.error}")
            self.assertEqual(self.node.get_total_supply(), TOTAL_SUPPLY)
            self.assertTrue(self.node.check_supply_invariant())
            self.assertTrue(self.node.check_balance_invariant())


class StakeTests(unittest.TestCase):
    def setUp(self):
        self.node, self.wallets = make_node()

    def test_stake_moves_balance_to_stake(self):
        sender = self.wallets[0]
        amount = 10 * ONE_TACH
        before_balance = self.node.get_balance(sender.address)
        result = self.node.submit_transaction(
            TachoinTx.build_stake(sender, amount, self.wallets[1].address, 0, 1)
        )
        self.assertTrue(result.success, result.error)
        self.assertEqual(self.node.get_balance(sender.address), before_balance - amount)
        self.assertEqual(self.node.get_stake(sender.address), amount)
        self.assertTrue(self.node.check_balance_invariant())

    def test_stake_to_unknown_validator_rejected(self):
        sender = self.wallets[0]
        outsider = TachoinWallet.generate()
        result = self.node.submit_transaction(
            TachoinTx.build_stake(sender, ONE_TACH, outsider.address, 0, 1)
        )
        self.assertFalse(result.success)
        self.assertIn("unknown validator", result.error)

    def test_unstake_returns_balance(self):
        sender = self.wallets[0]
        self.node.submit_transaction(
            TachoinTx.build_stake(sender, 10 * ONE_TACH, sender.address, 0, 1)
        )
        before = self.node.get_balance(sender.address)
        result = self.node.submit_transaction(
            TachoinTx.build_unstake(sender, 4 * ONE_TACH, sender.address, 1, 1)
        )
        self.assertTrue(result.success, result.error)
        self.assertEqual(self.node.get_balance(sender.address), before + 4 * ONE_TACH)
        self.assertEqual(self.node.get_stake(sender.address), 6 * ONE_TACH)
        self.assertTrue(self.node.check_balance_invariant())

    def test_unstake_more_than_staked_rejected(self):
        sender = self.wallets[0]
        result = self.node.submit_transaction(
            TachoinTx.build_unstake(sender, ONE_TACH, sender.address, 0, 1)
        )
        self.assertFalse(result.success)
        self.assertIn("insufficient stake", result.error)


class BlockTests(unittest.TestCase):
    def setUp(self):
        self.node, self.wallets = make_node()

    def test_genesis_block_is_recorded(self):
        self.assertEqual(len(self.node.ledger.blocks), 1)
        self.assertEqual(self.node.get_current_slot(), 0)

    def test_produce_block_advances_slot_and_ledger(self):
        block = self.node.produce_block()
        self.assertEqual(block.header.slot, 1)
        self.assertEqual(self.node.get_current_slot(), 1)
        self.assertEqual(len(self.node.ledger.blocks), 2)

    def test_block_includes_pending_transaction_once(self):
        sender = self.wallets[0]
        recipient = self.wallets[1].address
        amount = 10 * ONE_TACH
        before = self.node.get_balance(recipient)

        self.node.submit_transaction(
            TachoinTx.build_transfer(sender, recipient, amount, 0, 1)
        )
        mid = self.node.get_balance(recipient)
        self.assertEqual(mid, before + amount)

        block = self.node.produce_block()
        self.assertEqual(len(block.transactions), 1)
        self.assertEqual(self.node.get_balance(recipient), mid)
        self.assertEqual(self.node.pending_transactions(), [])

    def test_state_root_changes_after_transaction(self):
        before = self.node.state.root()
        self.node.submit_transaction(
            TachoinTx.build_transfer(
                self.wallets[0], self.wallets[1].address, ONE_TACH, 0, 1
            )
        )
        self.assertNotEqual(self.node.state.root(), before)

    def test_produce_blocks_with_transfers_keeps_invariants(self):
        blocks = self.node.produce_blocks(5, transactions_per_block=2)
        self.assertEqual(len(blocks), 5)
        self.assertTrue(self.node.check_supply_invariant())
        self.assertTrue(self.node.check_balance_invariant())

    def test_produce_blocks_rejects_non_positive_count(self):
        with self.assertRaises(ValueError):
            self.node.produce_blocks(0)


class TransactionSerializationTests(unittest.TestCase):
    def setUp(self):
        self.wallet = TachoinWallet.generate()
        self.recipient = TachoinWallet.generate().address

    def test_json_roundtrip_preserves_identity(self):
        tx = TachoinTx.build_transfer(self.wallet, self.recipient, ONE_TACH, 0, 1)
        restored = TachoinTx.from_json(tx.to_json())
        self.assertEqual(tx.tx_hash(), restored.tx_hash())
        self.assertTrue(restored.verify())

    def test_tachyon_transaction_roundtrip(self):
        tx = TachoinTx.build_transfer(self.wallet, self.recipient, ONE_TACH, 0, 1)
        wrapped = TachoinTx.from_tachyon_transaction(tx.to_tachyon_transaction())
        self.assertEqual(tx.tx_hash(), wrapped.tx_hash())
        self.assertTrue(wrapped.verify())

    def test_tx_hash_changes_with_nonce(self):
        first = TachoinTx.build_transfer(self.wallet, self.recipient, ONE_TACH, 0, 1)
        second = TachoinTx.build_transfer(self.wallet, self.recipient, ONE_TACH, 1, 1)
        self.assertNotEqual(first.tx_hash(), second.tx_hash())

    def test_unknown_program_rejected(self):
        with self.assertRaises(TransactionError):
            TachoinTx(
                sender=self.wallet.address,
                nonce=0,
                program="teleport",
                payload=b"{}",
                slot=1,
            )

    def test_negative_amount_rejected(self):
        with self.assertRaises(TransactionError):
            encode_transfer(self.recipient, -1)


class ClientTests(unittest.TestCase):
    """The convenience client must pass arguments in each builder's order.

    The suite previously only called ``TachoinTx.build_stake`` directly, which
    hid a real bug: ``TachoinClient._submit`` forwarded ``*extra`` after
    ``nonce, slot`` while ``build_stake`` expects ``validator`` third, so the
    integer nonce landed in the validator slot and every ``client.stake()``
    raised ``TransactionError``.
    """

    def setUp(self):
        from tachoin.client import TachoinClient

        self.client = TachoinClient(num_validators=4)
        self.sender, self.other = self.client.validator_wallets()[:2]

    def test_stake_defaults_to_own_address(self):
        result = self.client.stake(self.sender, "100")
        self.assertTrue(result["success"], result["error"])
        self.assertEqual(result["nonce"], 0)
        self.assertEqual(self.client.node.get_stake(self.sender.address), 100 * ONE_TACH)

    def test_stake_to_explicit_validator(self):
        # The SMT is the source of truth for token stake; the ledger is
        # synchronised from it at block-production time.  Produce a block
        # first so the ledger reflects the new delegation before we assert.
        result = self.client.stake(self.sender, "50", self.other.address)
        self.assertTrue(result["success"], result["error"])
        # Staker's token bucket, verified immediately via the SMT.
        self.assertEqual(self.client.node.get_stake(self.sender.address), 50 * ONE_TACH)
        # Ledger stake for the validator, verified after block production.
        self.client.node.produce_block()
        self.assertEqual(
            self.client.node.ledger.get_stake(self.other.address),
            250000 * ONE_TACH + 50 * ONE_TACH,
        )

    def test_unstake_to_explicit_validator(self):
        result = self.client.stake(self.sender, "80", self.other.address)
        self.assertTrue(result["success"], result["error"])
        self.client.node.produce_block()
        self.assertEqual(
            self.client.node.ledger.get_stake(self.other.address),
            250000 * ONE_TACH + 80 * ONE_TACH,
        )
        unstake_result = self.client.unstake(self.sender, "30", self.other.address)
        self.assertTrue(unstake_result["success"], unstake_result["error"])
        self.client.node.produce_block()
        self.assertEqual(self.client.node.get_stake(self.sender.address), 50 * ONE_TACH)
        self.assertEqual(
            self.client.node.ledger.get_stake(self.other.address),
            250000 * ONE_TACH + 50 * ONE_TACH,
        )

    def test_ledger_syncs_from_smt_at_block_production(self):
        """Regression: _apply_stake/_apply_unstake no longer write the ledger
        directly, so the two stores must match only after produce_block()."""
        self.client.stake(self.sender, "40", self.other.address)
        # Before block production the ledger still shows the genesis stake.
        self.assertEqual(
            self.client.node.ledger.get_stake(self.other.address),
            250000 * ONE_TACH,
        )
        # After block production the ledger reflects the SMT value.
        self.client.node.produce_block()
        self.assertEqual(
            self.client.node.ledger.get_stake(self.other.address),
            250000 * ONE_TACH + 40 * ONE_TACH,
        )
        # And the staker's SMT bucket matches what the ledger claims.
        self.assertEqual(
            self.client.node.get_stake(self.sender.address),
            40 * ONE_TACH,
        )

    def test_unstake_returns_balance(self):
        self.assertTrue(self.client.stake(self.sender, "100")["success"])
        result = self.client.unstake(self.sender, "40")
        self.assertTrue(result["success"], result["error"])
        self.assertEqual(self.client.node.get_stake(self.sender.address), 60 * ONE_TACH)

    def test_unstake_to_explicit_validator(self):
        self.assertTrue(self.client.stake(self.sender, "80", self.other.address)["success"])
        self.client.node.produce_block()
        self.assertEqual(
            self.client.node.ledger.get_stake(self.other.address),
            250000 * ONE_TACH + 80 * ONE_TACH,
        )
        result = self.client.unstake(self.sender, "30", self.other.address)
        self.assertTrue(result["success"], result["error"])
        self.client.node.produce_block()
        self.assertEqual(self.client.node.get_stake(self.sender.address), 50 * ONE_TACH)
        self.assertEqual(
            self.client.node.ledger.get_stake(self.other.address),
            250000 * ONE_TACH + 50 * ONE_TACH,
        )

    def test_client_nonces_advance_across_programs(self):
        self.assertEqual(self.client.transfer(self.sender, self.other.address, "1")["nonce"], 0)
        self.assertEqual(self.client.mint(self.sender, "2")["nonce"], 1)
        self.assertEqual(self.client.stake(self.sender, "3")["nonce"], 2)
        self.assertEqual(self.client.unstake(self.sender, "1")["nonce"], 3)

    def test_failed_client_transaction_consumes_no_nonce(self):
        failed = self.client.unstake(self.sender, "999999")
        self.assertFalse(failed["success"])
        self.assertEqual(self.client.node.get_nonce(self.sender.address), 0)

    def test_client_keeps_invariants(self):
        self.client.transfer(self.sender, self.other.address, "10")
        self.client.stake(self.sender, "20")
        self.client.mint(self.sender, "30")
        self.client.burn(self.sender, "5")
        self.assertTrue(self.client.node.check_supply_invariant())
        self.assertTrue(self.client.node.check_balance_invariant())


class StateKeyTests(unittest.TestCase):
    """Every sparse Merkle tree key must be a 32-byte digest.

    Tachyon's SMT is a 256-bit tree: ``set`` walks exactly 32 bytes and current
    releases reject any other length with ``SMT key must be exactly 32 bytes``.
    Tachoin 1.0.1 shipped 20-byte literal protocol keys, so importing the node
    raised on any up-to-date Tachyon checkout while passing against a stale one.
    These tests pin the invariant so a literal cannot be reintroduced.
    """

    ADDRESS = TachoinWallet(seed=bytes([7]) * 32).address

    def test_protocol_state_keys_are_32_bytes(self):
        from tachoin import config

        for name in (
            "STATE_KEY_TOTAL_SUPPLY",
            "STATE_KEY_CIRCULATING_SUPPLY",
            "STATE_KEY_UNCIRCULATED_SUPPLY",
            "STATE_KEY_BURNED_SUPPLY",
        ):
            key = getattr(config, name)
            self.assertIsInstance(key, bytes, name)
            self.assertEqual(len(key), 32, f"{name} must be 32 bytes")

    def test_account_keys_are_32_bytes(self):
        from tachoin.config import balance_key, nonce_key, stake_key

        for builder in (balance_key, stake_key, nonce_key):
            key = builder(self.ADDRESS)
            self.assertIsInstance(key, bytes)
            self.assertEqual(len(key), 32, builder.__name__)

    def test_key_families_do_not_collide(self):
        from tachoin import config
        from tachoin.config import balance_key, nonce_key, stake_key

        keys = [
            config.STATE_KEY_TOTAL_SUPPLY,
            config.STATE_KEY_CIRCULATING_SUPPLY,
            config.STATE_KEY_UNCIRCULATED_SUPPLY,
            config.STATE_KEY_BURNED_SUPPLY,
            balance_key(self.ADDRESS),
            stake_key(self.ADDRESS),
            nonce_key(self.ADDRESS),
        ]
        self.assertEqual(len(set(keys)), len(keys), "state keys must be unique")

    def test_node_initialises_and_conserves_supply(self):
        node, _ = make_node(2)
        self.assertTrue(node.check_supply_invariant())
        self.assertTrue(node.check_balance_invariant())


class SecurityTests(unittest.TestCase):
    """Regression tests for the two security fixes from the vulnerability report."""

    def setUp(self):
        self.node, self.wallets = make_node(4)
        self.sender = self.wallets[0]
        self.recipient = self.wallets[1]

    def test_fee_bypass_rejected(self):
        """Vulnerability #1: a transfer crafted with fee=0 must be rejected.

        Before the fix, _apply_transfer read the fee from the payload with
        `data.get("fee", TRANSFER_FEE)` so an attacker could set fee=0 and
        skip the validator payout entirely.
        """
        from tachoin.config import TRANSFER_FEE
        from tachoin.transaction import TachoinTx, encode_transfer

        # Craft a transfer with fee=0 — must fail at submission.
        payload = encode_transfer(self.recipient.address, 10**18, fee=0)
        tx = TachoinTx.build(
            self.sender,
            "transfer",
            payload,
            self.node.get_nonce(self.sender.address),
            self.node.get_current_slot() + 1,
        )
        result = self.node.submit_transaction(tx)
        self.assertFalse(result.success)
        self.assertIn("fee must be at least", result.error)
        # Balance must be unchanged.
        self.assertEqual(
            self.node.get_balance(self.sender.address),
            250000 * ONE_TACH,
        )

    def test_fee_below_minimum_rejected(self):
        """A transfer with fee < TRANSFER_FEE must also be rejected."""
        from tachoin.transaction import TachoinTx, encode_transfer

        payload = encode_transfer(self.recipient.address, 10**18, fee=1)
        tx = TachoinTx.build(
            self.sender,
            "transfer",
            payload,
            self.node.get_nonce(self.sender.address),
            self.node.get_current_slot() + 1,
        )
        result = self.node.submit_transaction(tx)
        self.assertFalse(result.success)
        self.assertIn("fee must be at least", result.error)

    def test_normal_transfer_still_succeeds(self):
        """Sanity check: a transfer with the default fee still works."""
        result = self.node.submit_transaction(
            TachoinTx.build_transfer(
                self.sender,
                self.recipient.address,
                10**18,
                self.node.get_nonce(self.sender.address),
                self.node.get_current_slot() + 1,
            )
        )
        self.assertTrue(result.success, result.error)

    def test_slot_freshness_rejects_far_future_slot(self):
        """Vulnerability #2: a transaction signed far ahead of the current slot
        must be rejected, preventing replay of stale pre-signed transactions."""
        from tachoin.config import SLOT_FRESHNESS_SLOTS
        from tachoin.transaction import TachoinTx

        far_slot = self.node.get_current_slot() + SLOT_FRESHNESS_SLOTS + 10
        tx = TachoinTx.build_transfer(
            self.sender,
            self.recipient.address,
            10**18,
            self.node.get_nonce(self.sender.address),
            far_slot,
        )
        result = self.node.submit_transaction(tx)
        self.assertFalse(result.success)
        self.assertIn("slot", result.error.lower())

    def test_slot_freshness_allows_within_window(self):
        """A transaction signed within the freshness window must be accepted."""
        from tachoin.config import SLOT_FRESHNESS_SLOTS
        from tachoin.transaction import TachoinTx

        ok_slot = self.node.get_current_slot() + SLOT_FRESHNESS_SLOTS
        tx = TachoinTx.build_transfer(
            self.sender,
            self.recipient.address,
            10**18,
            self.node.get_nonce(self.sender.address),
            ok_slot,
        )
        result = self.node.submit_transaction(tx)
        self.assertTrue(result.success, result.error)

    def test_mempool_bound_rejects_when_full(self):
        """Vulnerability #5: when the mempool is full, new submissions must
        be rejected with a clear error rather than growing memory unbounded.

        The mempool guard fires after the slot-freshness check but before
        the nonce check, so we fill ``_pending`` directly and verify the
        rejection path.
        """
        from tachoin.config import MAX_PENDING_TXS
        from tachoin.transaction import TachoinTx

        node, wallets = make_node(4)
        sender, recipient = wallets[0], wallets[1]

        # Simulate a full mempool without submitting MAX_PENDING_TXS real txs.
        node._pending = [None] * MAX_PENDING_TXS

        tx = TachoinTx.build_transfer(
            sender,
            recipient.address,
            10 ** 18,
            node.get_nonce(sender.address),
            node.get_current_slot() + 1,
        )
        result = node.submit_transaction(tx)
        self.assertFalse(result.success)
        self.assertIn("mempool is full", result.error)



class PackageTests(unittest.TestCase):
    def test_version_is_release_shaped(self):
        parts = tachoin.__version__.split(".")
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(part.isdigit() for part in parts))

    def test_public_api_is_exported(self):
        for name in ("TachoinWallet", "TachoinTx", "TransactionError"):
            self.assertTrue(hasattr(tachoin, name), name)

    def test_token_metadata(self):
        self.assertEqual(tachoin.TOKEN_SYMBOL, "TACH")
        self.assertEqual(tachoin.TOKEN_DECIMALS, 18)
        self.assertEqual(tachoin.TOTAL_SUPPLY, TOTAL_SUPPLY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
