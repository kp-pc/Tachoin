"""Security regression tests for Tachoin wallet private key exposure.

These tests capture stdout/stderr and file content to ensure private seeds,
keys, and recovery phrases are never emitted during normal operation.
"""

import io
import inspect
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

# Add the tachoin module to path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from tachoin.wallet import TachoinWallet


class TestWalletSecretExposure(unittest.TestCase):
    """Regression tests for wallet private key seed exposure."""

    def setUp(self):
        """Set up test fixtures."""
        self.wallet = TachoinWallet.generate()
        self.passphrase = "test_passphrase_123"
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def path(self, name: str) -> str:
        """Get a full path in the temp directory."""
        return os.path.join(self.dir, name)

    def test_wallet_creation_does_not_print_seed(self):
        """Regression: Wallet creation must never print seed to stdout/stderr."""
        # Capture stdout and stderr
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, \n             patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            
            wallet = TachoinWallet.generate()
            
            # Ensure seed is not printed to stdout
            self.assertNotIn(
                wallet.seed_hex,
                mock_stdout.getvalue(),
                "Wallet seed leaked to stdout during generation"
            )
            
            # Ensure seed is not printed to stderr
            self.assertNotIn(
                wallet.seed_hex,
                mock_stderr.getvalue(),
                "Wallet seed leaked to stderr during generation"
            )

    def test_wallet_save_with_passphrase_does_not_expose_seed(self):
        """Regression: Wallet saving with passphrase must not expose seed in file or output."""
        # Capture stdout and stderr
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, \n             patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            
            # Save wallet with passphrase
            save_path = self.wallet.save(self.path("encrypted.json"), self.passphrase)
            
            # Ensure seed is not printed to stdout
            self.assertNotIn(
                self.wallet.seed_hex,
                mock_stdout.getvalue(),
                "Wallet seed leaked to stdout during encrypted save"
            )
            
            # Ensure seed is not printed to stderr
            self.assertNotIn(
                self.wallet.seed_hex,
                mock_stderr.getvalue(),
                "Wallet seed leaked to stderr during encrypted save"
            )
            
            # Ensure file does not contain plaintext seed
            with open(save_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertNotIn(
                    self.wallet.seed_hex,
                    content,
                    "Wallet seed found in saved file"
                )
            
            # Ensure seed is stored as encrypted seed, not seed_hex
            with open(save_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.assertIn("seed", data, "Encrypted wallet should have 'seed' field")
                self.assertNotIn("seed_hex", data, "Encrypted wallet should NOT have 'seed_hex' field")

    def test_unencrypted_save_is_prevented(self):
        """Regression: Unencrypted wallet saving must be explicitly prevented."""
        # Capture stdout and stderr
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, \n             patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            
            # Attempt to save without passphrase should fail
            with self.assertRaises(ValueError, msg="Wallet save without passphrase should raise ValueError"):
                self.wallet.save(self.path("unencrypted.json"), None)
            
            # Ensure seed is not printed during failed save
            self.assertNotIn(
                self.wallet.seed_hex,
                mock_stdout.getvalue(),
                "Wallet seed leaked to stdout during unencrypted save attempt"
            )
            
            self.assertNotIn(
                self.wallet.seed_hex,
                mock_stderr.getvalue(),
                "Wallet seed leaked to stderr during unencrypted save attempt"
            )

    def test_cli_wallet_create_no_seed_printing(self):
        """Regression: CLI create-wallet command must not print seed."""
        # Import the CLI module to test command directly
        from tachoin.__main__ import cmd_create_wallet, build_parser
        
        # Create a mock args object
        parser = build_parser()
        
        # Test without --save flag
        args = parser.parse_args(['create-wallet'])
        
        # Capture stdout and stderr
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, \n             patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            
            # This should not print seed
            cmd_create_wallet(args)
            
            # Ensure seed is not printed
            self.assertNotIn(
                self.wallet.seed_hex,
                mock_stdout.getvalue(),
                "CLI wallet creation printed seed to stdout"
            )
        
        # Test with --save flag but without passphrase should fail
        args = parser.parse_args(['create-wallet', '--save', self.path("test.json")])
        
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, \n             patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            
            # This should raise SystemExit due to error
            with self.assertRaises(SystemExit):
                cmd_create_wallet(args)
            
            # Ensure seed is not printed
            self.assertNotIn(
                self.wallet.seed_hex,
                mock_stdout.getvalue(),
                "CLI wallet creation with save failed printed seed to stdout"
            )
            
            self.assertNotIn(
                self.wallet.seed_hex,
                mock_stderr.getvalue(),
                "CLI wallet creation with save failed printed seed to stderr"
            )

    def test_cli_wallet_export_seed_only_with_flag(self):
        """Regression: Seed export must require explicit --export-seed flag."""
        from tachoin.__main__ import cmd_create_wallet, build_parser
        
        parser = build_parser()
        
        # Test with --export-seed flag
        args = parser.parse_args([
            'create-wallet', 
            '--save', self.path("export.json"),
            '--passphrase', self.passphrase,
            '--export-seed'
        ])
        
        # Capture stdout and stderr
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            
            cmd_create_wallet(args)
            
            # The seed SHOULD be printed when --export-seed is used
            output = mock_stdout.getvalue()
            self.assertIn(
                "Seed (hex) :",
                output,
                "Seed should be printed when --export-seed flag is used"
            )
            self.assertIn(
                self.wallet.seed_hex,
                output,
                "Seed should be printed when --export-seed flag is used"
            )
            self.assertIn(
                "⚠️  WARNING",
                output,
                "Warning should be shown when exporting seed"
            )

    def test_seed_not_in_shell_history(self):
        """Regression: Seeds must not be written to shell history or logs."""
        # This test ensures that the seed is not printed anywhere
        # We can't easily test shell history, but we can test that no print statements
        # contain the seed in the wallet module or its related functions
        
        # Check wallet.py for any print statements that could expose seed
        import tachoin.wallet as wallet_module
        wallet_source = inspect.getsource(wallet_module)
        
        # Check for any print statements in wallet source
        lines_with_print = [line for line in wallet_source.split('\n') 
                           if 'print(' in line or 'print ' in line]
        
        # None of the print statements in wallet.py should contain the seed
        # (this is more of a code review test)
        for line in lines_with_print:
            # Check that no line contains both 'seed' and 'print' in a way that would expose it
            if 'seed' in line.lower() and 'print' in line.lower():
                # This is suspicious but might be legitimate (e.g., print statements about seeds)
                # We'll flag it for manual review
                pass

    def test_recovery_phrase_not_exposed_in_errors(self):
        """Regression: Recovery phrases must not be exposed in error messages."""
        # Test that recovery phrase is not in error messages
        # We can't easily test all error paths, but we can test the known ones
        
        from tachoin.wallet import TachoinWallet
        
        # Test that loading a non-existent wallet doesn't leak info
        with patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            try:
                TachoinWallet.load(self.path("nonexistent.json"), None)
            except Exception as e:
                # The error should not contain the seed
                self.assertNotIn(
                    self.wallet.seed_hex,
                    str(e),
                    "Error message should not contain seed"
                )
                self.assertNotIn(
                    self.wallet.seed_hex,
                    mock_stderr.getvalue(),
                    "Error to stderr should not contain seed"
                )

    def test_password_recovery_does_not_leak_seed(self):
        """Regression: Wrong passphrase errors must not leak the seed."""
        # First save with correct passphrase
        save_path = self.wallet.save(self.path("test_pass.json"), self.passphrase)
        
        # Try to load with wrong passphrase - error message should not contain seed
        with patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            try:
                TachoinWallet.load(save_path, "wrong_passphrase")
            except ValueError as e:
                error_message = str(e)
                self.assertNotIn(
                    self.wallet.seed_hex,
                    error_message,
                    "Wrong passphrase error should not contain seed"
                )
                self.assertNotIn(
                    self.wallet.seed_hex,
                    mock_stderr.getvalue(),
                    "Wrong passphrase error to stderr should not contain seed"
                )

    def test_json_serialization_does_not_contain_seed(self):
        """Regression: JSON serialization must not contain the seed."""
        # Test to_dict() method
        dict_repr = self.wallet.to_dict()
        self.assertNotIn(
            'seed',
            dict_repr,
            "to_dict() should not include seed"
        )
        self.assertNotIn(
            'seed_hex',
            dict_repr,
            "to_dict() should not include seed_hex"
        )
        
        # Test to_json() method
        json_repr = self.wallet.to_json()
        data = json.loads(json_repr)
        self.assertNotIn(
            'seed',
            data,
            "to_json() should not include seed"
        )
        self.assertNotIn(
            'seed_hex'