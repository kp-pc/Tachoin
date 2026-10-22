import unittest
import json
from tachoin.node import TachoinNode, make_node
from tachoin.transaction import TachoinTx
from tachoin.config import TRANSFER_FEE, TOKEN_DECIMALS
from tachoin.wallet import TachoinWallet

ONE_TACH = 10 ** TOKEN_DECIMALS

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.node, self.wallets = make_node(4)
        self.sender = self.wallets[0]

    def test_malformed_payload_does_not_crash_node(self):
        """Regression: Ensure malformed payloads return an error instead of crashing."""
        tx = TachoinTx.build(self.sender, "transfer", b"invalid json", 0, 1)
        result = self.node.submit_transaction(tx)
        self.assertFalse(result.success)
        self.assertIn("JSON", result.error)

    def test_unstake_validator_field_enforcement(self):
        """Ensure unstaking validates the validator field correctly."""
        # This test ensures that unstaking to an unknown address is rejected.
        unknown_validator = TachoinWallet.generate().address
        tx = TachoinTx.build(
            self.sender,
            "unstake",
            json.dumps({"type": "unstake", "amount": 1 * ONE_TACH, "validator": unknown_validator}).encode(),
            0,
            1
        )
        result = self.node.submit_transaction(tx)
        self.assertFalse(result.success, "Unstake to unknown validator should be rejected")

    def test_slot_freshness_enforcement(self):
        """Ensure slot freshness lower bound is enforced to prevent fee evasion."""
        # Slot 0 is genesis, current slot is 0, so slot < -2 (SLOT_FRESHNESS_SLOTS=2)
        # should be rejected. This is already tested but ensuring we understand the boundary.
        # Attempting to submit at genesis slot with slot -5.
        tx = TachoinTx.build_transfer(self.sender, self.wallets[1].address, 1 * ONE_TACH, 0, -5)
        result = self.node.submit_transaction(tx)
        self.assertFalse(result.success)
        self.assertIn("too old", result.error)

    def test_arithmetic_boundaries(self):
        """Test boundary conditions for amounts."""
        # Test zero amount
        tx = TachoinTx.build(
            self.sender, 
            "transfer", 
            json.dumps({"type": "transfer", "to": self.wallets[1].address, "amount": 0, "fee": TRANSFER_FEE}).encode(),
            0,
            1
        )
        result = self.node.submit_transaction(tx)
        self.assertFalse(result.success)

        # Test negative amount (should fail schema validation if implemented, or node handler)
        tx = TachoinTx.build(
            self.sender, 
            "transfer", 
            json.dumps({"type": "transfer", "to": self.wallets[1].address, "amount": -1, "fee": TRANSFER_FEE}).encode(),
            0,
            1
        )
        result = self.node.submit_transaction(tx)
        self.assertFalse(result.success)

if __name__ == '__main__':
    unittest.main()
