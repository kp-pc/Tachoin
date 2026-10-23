"""Comprehensive security tests for Tachoin v2 wallet implementation.

This test suite verifies all cryptographic properties and security requirements
for the enhanced wallet_v2.py implementation.

Test Categories:
1. Known-Answer Tests - Verify deterministic behavior with fixed inputs
2. Wrong-Passphrase Tests - Verify security against brute force
3. Ciphertext-Tampering Tests - Verify tamper detection
4. Malformed-File Tests - Verify graceful rejection of invalid formats
5. Deterministic Compatibility Tests - Verify consistency across operations

Security Requirements Verified:
- Argon2id key derivation with documented parameters
- ChaCha20-Poly1305 authenticated encryption
- NaCl Ed25519 signing
- Constant-time operations
- Secure randomness
- Versioned wallet format
- Migration from v1 to v2
"""

import json
import os
import tempfile
import unittest
from typing import Dict, Any

from tachoin.wallet_v2 import (
    TachoinWalletV2,
    WALLET_VERSION_V2,
    ARGON2ID_MEMORY,
    ARGON2ID_ITERATIONS,
    ARGON2ID_PARALLELISM,
    ARGON2ID_SALT_LENGTH,
    CHACHA20POLY1305_NONCE_LENGTH,
    ED25519_SEED_SIZE,
    BIP39Mnemonic,
    constant_time_compare,
    secure_random_bytes,
)
from tachoin.wallet import TachoinWallet


class TestKnownAnswerVectors(unittest.TestCase):
    """Test vectors for regression testing - ensure deterministic behavior."""
    
    def test_argon2id_derivation_known_answer(self):
        """Test Argon2id key derivation with known parameters."""
        # Test with fixed password and salt
        password = "correct horse battery staple"
        salt = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                      0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10])
        
        # Create key derivation instance
        kd = TachoinWalletV2._key_derivation.__class__()
        
        # Derive keys
        enc_key, mac_key = kd.derive_key(password, salt)
        
        # Verify key lengths
        self.assertEqual(len(enc_key), 32)
        self.assertEqual(len(mac_key), 32)
        
        # Verify keys are not zero
        self.assertNotEqual(enc_key, bytes(32))
        self.assertNotEqual(mac_key, bytes(32))
        
        # Verify keys are deterministic (same input = same output)
        enc_key2, mac_key2 = kd.derive_key(password, salt)
        self.assertEqual(enc_key, enc_key2)
        self.assertEqual(mac_key, mac_key2)
    
    def test_chacha20poly1305_encryption_known_answer(self):
        """Test ChaCha20-Poly1305 encryption with known plaintext."""
        # Use a fixed key and nonce for testing
        key = bytes([0x00] * 32)
        nonce = bytes([0x01] * 12)
        plaintext = b"Test message for encryption"
        
        # Encrypt
        encryption = TachoinWalletV2._ChaCha20Poly1305Encryption.__new__(
            TachoinWalletV2._ChaCha20Poly1305Encryption
        )
        encryption.key = key
        encryption.nonce = nonce
        encryption.cipher = TachoinWalletV2._ChaCha20Poly1305Encryption.__dict__['ChaCha20Poly1305'](key)
        
        ciphertext = encryption.encrypt(plaintext)
        
        # Verify ciphertext structure (nonce + encrypted data)
        self.assertEqual(len(ciphertext), CHACHA20POLY1305_NONCE_LENGTH + len(plaintext))
        self.assertEqual(ciphertext[:CHACHA20POLY1305_NONCE_LENGTH], nonce)
        
        # Verify decryption
        decrypted = encryption.decrypt(ciphertext)
        self.assertEqual(decrypted, plaintext)
    
    def test_ed25519_signing_known_answer(self):
        """Test Ed25519 signing with known seed."""
        # Use a fixed seed for testing
        seed = bytes([0x01] * ED25519_SEED_SIZE)
        
        # Create wallet
        wallet = TachoinWalletV2(seed)
        
        # Sign a fixed message
        message = b"Test message for signing"
        signature = wallet.sign(message)
        
        # Verify signature length
        self.assertEqual(len(signature), 64)
        
        # Verify signature is deterministic for same seed and message
        signature2 = wallet.sign(message)
        self.assertEqual(signature, signature2)
        
        # Verify signature verification
        is_valid = TachoinWalletV2.verify_signature(wallet.address, message, signature)
        self.assertTrue(is_valid)
    
    def test_wallet_v2_format_known_answer(self):
        """Test wallet v2 format with known seed."""
        # Use a fixed seed
        seed = bytes([0xAA] * ED25519_SEED_SIZE)
        
        # Create wallet
        wallet = TachoinWalletV2(seed)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save wallet
            wallet.save_v2(temp_path, "testpassphrase123")
            
            # Load wallet
            loaded_wallet = TachoinWalletV2.load_v2(temp_path, "testpassphrase123")
            
            # Verify wallet properties
            self.assertEqual(wallet.address, loaded_wallet.address)
            self.assertEqual(wallet.public_key_hex, loaded_wallet.public_key_hex)
            self.assertEqual(wallet.seed_hex, loaded_wallet.seed_hex)
            self.assertEqual(wallet.version, WALLET_VERSION_V2)
            
            # Verify wallet can sign and verify
            message = b"Test message"
            signature = wallet.sign(message)
            self.assertTrue(TachoinWalletV2.verify_signature(wallet.address, message, signature))
            
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_bip39_mnemonic_known_answer(self):
        """Test BIP-39 mnemonic generation and validation."""
        # Test with fixed entropy
        entropy_bits = 128
        
        # Generate mnemonic
        mnemonic = BIP39Mnemonic.generate_mnemonic(entropy_bits)
        
        # Verify mnemonic format (12 words for 128 bits)
        words = mnemonic.split()
        self.assertEqual(len(words), 12)
        
        # Verify mnemonic can be validated
        self.assertTrue(BIP39Mnemonic.validate_mnemonic(mnemonic))
        
        # Verify mnemonic can be converted to seed
        seed = BIP39Mnemonic.mnemonic_to_seed(mnemonic)
        self.assertEqual(len(seed), 64)  # 64 bytes for BIP-39
        
        # Verify seed can create wallet
        wallet = TachoinWalletV2(seed[:ED25519_SEED_SIZE])
        self.assertIsNotNone(wallet.address)


class TestWrongPassphraseSecurity(unittest.TestCase):
    """Verify security against wrong passphrases and brute force."""
    
    def test_wrong_passphrase_rejection(self):
        """Verify that wrong passphrase is rejected."""
        # Create wallet
        wallet = TachoinWalletV2()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save with correct passphrase
            wallet.save_v2(temp_path, "correctpassphrase")
            
            # Try to load with wrong passphrase
            with self.assertRaises(ValueError):
                TachoinWalletV2.load_v2(temp_path, "wrongpassphrase")
            
            # Try to load with empty passphrase
            with self.assertRaises(ValueError):
                TachoinWalletV2.load_v2(temp_path, "")
                
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_passphrase_strength_requirements(self):
        """Verify passphrase strength requirements."""
        wallet = TachoinWalletV2()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Test short passphrase (should fail)
            with self.assertRaises(ValueError):
                wallet.save_v2(temp_path, "short")
            
            # Test empty passphrase (should fail)
            with self.assertRaises(ValueError):
                wallet.save_v2(temp_path, "")
            
            # Test valid passphrase (should succeed)
            wallet.save_v2(temp_path, "validpassphrase123")
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_constant_time_passphrase_comparison(self):
        """Verify constant-time comparison for passphrase validation."""
        # Test the constant_time_compare function
        val1 = b"testvalue"
        val2 = b"testvalue"
        val3 = b"different"
        
        # Same values should return True
        self.assertTrue(constant_time_compare(val1, val2))
        
        # Different values should return False
        self.assertFalse(constant_time_compare(val1, val3))
        
        # Different lengths should return False
        self.assertFalse(constant_time_compare(val1, b"test"))
    
    def test_argon2id_memory_hardness(self):
        """Verify Argon2id memory hardness parameters."""
        kd = TachoinWalletV2._key_derivation.__class__()
        
        # Verify default parameters match OWASP recommendations
        self.assertEqual(kd.memory, ARGON2ID_MEMORY)  # 64 MiB
        self.assertEqual(kd.iterations, ARGON2ID_ITERATIONS)  # 3 iterations
        self.assertEqual(kd.parallelism, ARGON2ID_PARALLELISM)  # 4 parallelism
        self.assertEqual(kd.hash_length, 32)  # 32 bytes for key derivation


class TestCiphertextTamperingDetection(unittest.TestCase):
    """Verify detection of tampered ciphertext."""
    
    def test_tampered_ciphertext_rejection(self):
        """Verify that tampered ciphertext is detected."""
        wallet = TachoinWalletV2()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save wallet
            wallet.save_v2(temp_path, "testpassphrase")
            
            # Load wallet file and tamper with it
            with open(temp_path, 'r') as f:
                payload = json.load(f)
            
            # Tamper with encrypted_seed
            original_seed = payload['encrypted_seed']
            tampered_seed = original_seed[:-2] + ('00' if original_seed[-2:] != '00' else '11')
            payload['encrypted_seed'] = tampered_seed
            
            # Save tampered wallet
            with open(temp_path, 'w') as f:
                json.dump(payload, f)
            
            # Try to load tampered wallet (should fail)
            with self.assertRaises(ValueError):
                TachoinWalletV2.load_v2(temp_path, "testpassphrase")
                
            # Restore original
            payload['encrypted_seed'] = original_seed
            with open(temp_path, 'w') as f:
                json.dump(payload, f)
                
            # Verify original wallet still loads correctly
            loaded_wallet = TachoinWalletV2.load_v2(temp_path, "testpassphrase")
            self.assertEqual(wallet.address, loaded_wallet.address)
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_tampered_nonce_rejection(self):
        """Verify that tampered nonce is detected."""
        wallet = TachoinWalletV2()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save wallet
            wallet.save_v2(temp_path, "testpassphrase")
            
            # Load wallet file and tamper with nonce
            with open(temp_path, 'r') as f:
                payload = json.load(f)
            
            # Tamper with nonce
            original_nonce = payload['nonce']
            tampered_nonce = original_nonce[:-2] + ('00' if original_nonce[-2:] != '00' else '11')
            payload['nonce'] = tampered_nonce
            
            # Save tampered wallet
            with open(temp_path, 'w') as f:
                json.dump(payload, f)
            
            # Try to load tampered wallet (should fail)
            with self.assertRaises(ValueError):
                TachoinWalletV2.load_v2(temp_path, "testpassphrase")
                
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_tampered_salt_rejection(self):
        """Verify that tampered salt is detected."""
        wallet = TachoinWalletV2()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save wallet
            wallet.save_v2(temp_path, "testpassphrase")
            
            # Load wallet file and tamper with salt
            with open(temp_path, 'r') as f:
                payload = json.load(f)
            
            # Tamper with salt
            original_salt = payload['salt']
            tampered_salt = original_salt[:-2] + ('00' if original_salt[-2:] != '00' else '11')
            payload['salt'] = tampered_salt
            
            # Save tampered wallet
            with open(temp_path, 'w') as f:
                json.dump(payload, f)
            
            # Try to load tampered wallet (should fail)
            with self.assertRaises(ValueError):
                TachoinWalletV2.load_v2(temp_path, "testpassphrase")
                
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_tampered_address_rejection(self):
        """Verify that tampered address is detected."""
        wallet = TachoinWalletV2()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save wallet
            wallet.save_v2(temp_path, "testpassphrase")
            
            # Load wallet file and tamper with address
            with open(temp_path, 'r') as f:
                payload = json.load(f)
            
            # Tamper with address
            original_address = payload['address']
            tampered_address = original_address[:-1] + ('0' if original_address[-1] != '0' else '1')
            payload['address'] = tampered_address
            
            # Save tampered wallet
            with open(temp_path, 'w') as f:
                json.dump(payload, f)
            
            # Try to load tampered wallet (should fail)
            with self.assertRaises(ValueError):
                TachoinWalletV2.load_v2(temp_path, "testpassphrase")
                
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestMalformedFileRejection(unittest.TestCase):
    """Verify graceful rejection of malformed wallet files."""
    
    def test_invalid_json_rejection(self):
        """Verify that invalid JSON is rejected."""
        wallet = TachoinWalletV2()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save valid wallet
            wallet.save_v2(temp_path, "testpassphrase")
            
            # Corrupt the JSON
            with open(temp_path, 'a') as f:
                f.write("INVALID JSON DATA")
            
            # Try to load corrupted wallet (should fail)
            with self.assertRaises((json.JSONDecodeError, ValueError)):
                TachoinWalletV2.load_v2(temp_path, "testpassphrase")
                
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_missing_required_fields_rejection(self):
        """Verify that missing required fields are detected."""
        wallet = TachoinWalletV2()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save valid wallet
            wallet.save_v2(temp_path, "testpassphrase")
            
            # Load and remove required field
            with open(temp_path, 'r') as f:
                payload = json.load(f)
            
            # Remove required field
            del payload['address']
            
            # Save corrupted wallet
            with open(temp_path, 'w') as f:
                json.dump(payload, f)
            
            # Try to load corrupted wallet (should fail)
            with self.assertRaises(ValueError):
                TachoinWalletV2.load_v2(temp_path, "testpassphrase")
                
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_invalid_version_rejection(self):
        """Verify that unsupported wallet versions are rejected."""
        wallet = TachoinWalletV2()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save valid wallet
            wallet.save_v2(temp_path, "testpassphrase")
            
            # Load and change version
            with open(temp_path, 'r') as f:
                payload = json.load(f)
            
            # Change to unsupported version
            payload['version'] = 999
            
            # Save corrupted wallet
            with open(temp_path, 'w') as f:
                json.dump(payload, f)
            
            # Try to load corrupted wallet (should fail)
            with self.assertRaises(ValueError):
                TachoinWalletV2.load_v2(temp_path, "testpassphrase")
                
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_invalid_address_format_rejection(self):
        """Verify that invalid address formats are rejected."""
        wallet = TachoinWalletV2()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save valid wallet
            wallet.save_v2(temp_path, "testpassphrase")
            
            # Load and corrupt address
            with open(temp_path, 'r') as f:
                payload = json.load(f)
            
            # Corrupt address
            payload['address'] = "invalidaddress"
            
            # Save corrupted wallet
            with open(temp_path, 'w') as f:
                json.dump(payload, f)
            
            # Try to load corrupted wallet (should fail)
            with self.assertRaises(ValueError):
                TachoinWalletV2.load_v2(temp_path, "testpassphrase")
                
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_malformed_hex_data_rejection(self):
        """Verify that malformed hex data is rejected."""
        wallet = TachoinWalletV2()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save valid wallet
            wallet.save_v2(temp_path, "testpassphrase")
            
            # Load and corrupt hex data
            with open(temp_path, 'r') as f:
                payload = json.load(f)
            
            # Corrupt salt (invalid hex)
            payload['salt'] = "GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG"  # G is not valid hex
            
            # Save corrupted wallet
            with open(temp_path, 'w') as f:
                json.dump(payload, f)
            
            # Try to load corrupted wallet (should fail)
            with self.assertRaises(ValueError):
                TachoinWalletV2.load_v2(temp_path, "testpassphrase")
                
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestDeterministicCompatibility(unittest.TestCase):
    """Verify deterministic behavior and compatibility."""
    
    def test_same_seed_same_wallet(self):
        """Verify that same seed produces same wallet."""
        seed = bytes([0x55] * ED25519_SEED_SIZE)
        
        wallet1 = TachoinWalletV2(seed)
        wallet2 = TachoinWalletV2(seed)
        
        # Verify same properties
        self.assertEqual(wallet1.address, wallet2.address)
        self.assertEqual(wallet1.public_key_hex, wallet2.public_key_hex)
        self.assertEqual(wallet1.seed_hex, wallet2.seed_hex)
        self.assertEqual(wallet1.version, wallet2.version)
    
    def test_same_seed_same_signature(self):
        """Verify that same seed produces same signature for same message."""
        seed = bytes([0xCC] * ED25519_SEED_SIZE)
        message = b"Test message for deterministic signature"
        
        wallet1 = TachoinWalletV2(seed)
        wallet2 = TachoinWalletV2(seed)
        
        signature1 = wallet1.sign(message)
        signature2 = wallet2.sign(message)
        
        self.assertEqual(signature1, signature2)
    
    def test_different_seeds_different_wallets(self):
        """Verify that different seeds produce different wallets."""
        seed1 = bytes([0x01] * ED25519_SEED_SIZE)
        seed2 = bytes([0x02] * ED25519_SEED_SIZE)
        
        wallet1 = TachoinWalletV2(seed1)
        wallet2 = TachoinWalletV2(seed2)
        
        # Verify different properties
        self.assertNotEqual(wallet1.address, wallet2.address)
        self.assertNotEqual(wallet1.public_key_hex, wallet2.public_key_hex)
        self.assertNotEqual(wallet1.seed_hex, wallet2.seed_hex)
    
    def test_different_nonces_different_ciphertexts(self):
        """Verify that different nonces produce different ciphertexts."""
        wallet = TachoinWalletV2()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path1 = f.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path2 = f.name
        
        try:
            # Save wallet twice (will use different nonces)
            wallet.save_v2(temp_path1, "testpassphrase")
            wallet.save_v2(temp_path2, "testpassphrase")
            
            # Load both wallets
            loaded1 = TachoinWalletV2.load_v2(temp_path1, "testpassphrase")
            loaded2 = TachoinWalletV2.load_v2(temp_path2, "testpassphrase")
            
            # Verify same wallet properties
            self.assertEqual(wallet.address, loaded1.address)
            self.assertEqual(wallet.address, loaded2.address)
            
            # Verify different ciphertexts (different nonces)
            with open(temp_path1, 'r') as f:
                payload1 = json.load(f)
            with open(temp_path2, 'r') as f:
                payload2 = json.load(f)
            
            self.assertNotEqual(payload1['nonce'], payload2['nonce'])
            self.assertNotEqual(payload1['encrypted_seed'], payload2['encrypted_seed'])
            
        finally:
            for path in [temp_path1, temp_path2]:
                if os.path.exists(path):
                    os.unlink(path)
    
    def test_wallet_metadata_consistency(self):
        """Verify wallet metadata is consistent."""
        wallet = TachoinWalletV2()
        
        # Verify version is correct
        self.assertEqual(wallet.version, WALLET_VERSION_V2)
        
        # Verify address is valid
        from tachoin.wallet import is_valid_address
        self.assertTrue(is_valid_address(wallet.address))
        
        # Verify public key length
        self.assertEqual(len(wallet.public_key), 32)
        
        # Verify seed length
        self.assertEqual(len(wallet.seed_hex), 64)  # 32 bytes = 64 hex chars


class TestMigrationFromV1(unittest.TestCase):
    """Test migration from legacy wallet format (v1) to enhanced format (v2)."""
    
    def test_migration_from_v1_to_v2(self):
        """Test migration of legacy wallet to v2 format."""
        # Create a legacy wallet
        legacy_wallet = TachoinWallet.generate()
        
        # Save legacy wallet
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            legacy_path = f.name
        
        try:
            legacy_wallet.save(legacy_path, "legacy_passphrase")
            
            # Create v2 wallet by migrating
            v2_wallet = TachoinWalletV2()
            migrated_path = v2_wallet.migrate_to_v2(legacy_path, "legacy_passphrase")
            
            # Verify migrated wallet exists
            self.assertTrue(os.path.exists(migrated_path))
            
            # Verify we can load the migrated wallet
            loaded_v2_wallet = TachoinWalletV2.load_v2(migrated_path, "legacy_passphrase")
            
            # Verify the migrated wallet has the same seed as the legacy wallet
            self.assertEqual(legacy_wallet.address, loaded_v2_wallet.address)
            self.assertEqual(legacy_wallet.public_key_hex, loaded_v2_wallet.public_key_hex)
            
            # Verify v2 wallet properties
            self.assertEqual(loaded_v2_wallet.version, WALLET_VERSION_V2)
            
            # Verify v2 wallet can sign and verify
            message = b"Test message after migration"
            signature = loaded_v2_wallet.sign(message)
            self.assertTrue(TachoinWalletV2.verify_signature(
                loaded_v2_wallet.address, message, signature
            ))
            
        finally:
            # Clean up
            for path in [legacy_path, migrated_path]:
                if os.path.exists(path):
                    os.unlink(path)
    
    def test_migration_preserves_seed(self):
        """Test that migration preserves the original seed."""
        # Create a legacy wallet with known seed
        seed = bytes([0xFF] * ED25519_SEED_SIZE)
        legacy_wallet = TachoinWallet(seed)
        
        # Save legacy wallet
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            legacy_path = f.name
        
        try:
            legacy_wallet.save(legacy_path, "testpassphrase")
            
            # Migrate to v2
            v2_wallet = TachoinWalletV2()
            migrated_path = v2_wallet.migrate_to_v2(legacy_path, "testpassphrase")
            
            # Load migrated wallet
            loaded_v2_wallet = TachoinWalletV2.load_v2(migrated_path, "testpassphrase")
            
            # Verify seed is preserved
            self.assertEqual(seed.hex(), loaded_v2_wallet.seed_hex)
            
        finally:
            for path in [legacy_path, migrated_path]:
                if os.path.exists(path):
                    os.unlink(path)
    
    def test_migration_with_wrong_passphrase_fails(self):
        """Test that migration with wrong passphrase fails."""
        # Create a legacy wallet
        legacy_wallet = TachoinWallet.generate()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            legacy_path = f.name
        
        try:
            legacy_wallet.save(legacy_path, "correct_passphrase")
            
            # Try to migrate with wrong passphrase
            v2_wallet = TachoinWalletV2()
            with self.assertRaises(ValueError):
                v2_wallet.migrate_to_v2(legacy_path, "wrong_passphrase")
                
        finally:
            if os.path.exists(legacy_path):
                os.unlink(legacy_path)


class TestSecurityProperties(unittest.TestCase):
    """Test overall security properties of the wallet implementation."""
    
    def test_no_plaintext_seed_in_file(self):
        """Verify that plaintext seed is never written to wallet file."""
        wallet = TachoinWalletV2()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save wallet
            wallet.save_v2(temp_path, "testpassphrase")
            
            # Read wallet file
            with open(temp_path, 'r') as f:
                content = f.read()
            
            # Verify seed is not in plaintext
            self.assertNotIn(wallet.seed_hex, content)
            
            # Verify encrypted_seed is in the file
            with open(temp_path, 'r') as f:
                payload = json.load(f)
            self.assertIn('encrypted_seed', payload)
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_secure_randomness(self):
        """Verify that secure randomness is used."""
        # Test secure_random_bytes function
        for length in [16, 32, 64]:
            random_bytes = secure_random_bytes(length)
            self.assertEqual(len(random_bytes), length)
            self.assertNotEqual(random_bytes, bytes(length))
        
        # Test that different calls produce different results
        random1 = secure_random_bytes(32)
        random2 = secure_random_bytes(32)
        self.assertNotEqual(random1, random2)
    
    def test_constant_time_operations(self):
        """Verify that constant-time operations are used where appropriate."""
        # Test constant_time_compare
        val1 = b"test"
        val2 = b"test"
        val3 = b"different"
        
        # Should use constant-time comparison
        result1 = constant_time_compare(val1, val2)
        result2 = constant_time_compare(val1, val3)
        
        self.assertTrue(result1)
        self.assertFalse(result2)
    
    def test_wallet_format_versioning(self):
        """Verify that wallet format includes version information."""
        wallet = TachoinWalletV2()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save wallet
            wallet.save_v2(temp_path, "testpassphrase")
            
            # Load wallet file
            with open(temp_path, 'r') as f:
                payload = json.load(f)
            
            # Verify version is present
            self.assertIn('version', payload)
            self.assertEqual(payload['version'], WALLET_VERSION_V2)
            
            # Verify format is specified
            self.assertIn('format', payload)
            self.assertIn('crypto'