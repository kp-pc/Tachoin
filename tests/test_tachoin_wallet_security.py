"""Security regression tests for Tachoin wallet private key exposure.

These tests capture stdout/stderr and file content to ensure private seeds,
keys, and recovery phrases are never emitted during normal operation.
"""

import io
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
        self.wallet = TachoinWallet.generate()
        self.passphrase = "test_passphrase_123"
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.dir, name)

    def test_wallet_creation_does_not_print_seed(self):
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            wallet = TachoinWallet.generate()
            self.assertNotIn(wallet.seed_hex, mock_stdout.getvalue())
            self.assertNotIn(wallet.seed_hex, mock_stderr.getvalue())

    def test_wallet_save_with_passphrase_does_not_expose_seed(self):
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            save_path = self.wallet.save(self.path("encrypted.json"), self.passphrase)
            self.assertNotIn(self.wallet.seed_hex, mock_stdout.getvalue())
            self.assertNotIn(self.wallet.seed_hex, mock_stderr.getvalue())
            with open(save_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertNotIn(self.wallet.seed_hex, content)
            with open(save_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.assertIn("seed", data)
                self.assertNotIn("seed_hex", data)

    def test_unencrypted_save_is_prevented(self):
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            with self.assertRaises(ValueError):
                self.wallet.save(self.path("unencrypted.json"), None)
            self.assertNotIn(self.wallet.seed_hex, mock_stdout.getvalue())
            self.assertNotIn(self.wallet.seed_hex, mock_stderr.getvalue())

    def test_cli_wallet_create_no_seed_printing(self):
        from tachoin.__main__ import cmd_create_wallet, build_parser
        parser = build_parser()
        args = parser.parse_args(['create-wallet'])
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            cmd_create_wallet(args)
            self.assertNotIn(self.wallet.seed_hex, mock_stdout.getvalue())
        args = parser.parse_args(['create-wallet', '--save', self.path("test.json")])
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            with self.assertRaises(SystemExit):
                cmd_create_wallet(args)
            self.assertNotIn(self.wallet.seed_hex, mock_stdout.getvalue())
            self.assertNotIn(self.wallet.seed_hex, mock_stderr.getvalue())

    def test_cli_wallet_export_seed_only_with_flag(self):
        from tachoin.__main__ import cmd_create_wallet, build_parser
        parser = build_parser()
        args = parser.parse_args(['create-wallet', '--save', self.path("export.json"), '--passphrase', self.passphrase, '--export-seed'])
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            cmd_create_wallet(args)
            output = mock_stdout.getvalue()
            self.assertIn("Seed (hex) :", output)
            self.assertIn(self.wallet.seed_hex, output)
            self.assertIn("WARNING", output)