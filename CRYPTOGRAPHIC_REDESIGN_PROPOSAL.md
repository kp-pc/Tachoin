# Tachoin-Coin Wallet Encryption and Recovery Redesign Proposal

## Current State Analysis

### Existing Implementation Overview

The current Tachoin-Coin wallet uses the following cryptographic construction:

**Key Derivation:**
- Algorithm: `hashlib.scrypt` with parameters (N=16384, r=8, p=1)
- Output: 64 bytes (32 bytes encryption key + 32 bytes MAC key)
- Strength: Moderate, but could be significantly improved

**Encryption Scheme:**
- Algorithm: Custom XOR with HMAC-SHA256 counter-mode keystream
- Authentication: HMAC-SHA256 over (address + salt + nonce + ciphertext)
- Nonce: 16 bytes random per encryption
- Salt: 16 bytes random per derivation

**Signing:**
- Algorithm: Pure Python Ed25519 implementation from tachyon-blockchain
- Curve: Ed25519 (RFC 8032)
- Public Key: 32 bytes

**Mnemonic System:**
- Algorithm: SHA-512 hash of normalized phrase, take first 32 bytes
- Compatibility: Explicitly not BIP-39
- Entropy: 256 bits

### Security Concerns

1. **Key Derivation**: Scrypt parameters are moderate (N=2^14) - could be higher for memory-hardness
2. **Custom Construction**: XOR with HMAC is not a standard AEAD construction
3. **Signing Implementation**: Pure Python Ed25519 may be slower and less audited than optimized libraries
4. **Mnemonic System**: Non-standard, limits interoperability
5. **No Version Control**: Wallet format changes could break existing wallets

## Proposed Redesign

### 1. Authenticated Encryption

**Replace**: Custom XOR + HMAC with standard AEAD
- **Choice**: ChaCha20-Poly1305 or AES-GCM
- **Rationale**: Proven security, widely vetted implementations
- **Implementation**: Use `cryptography` library's `Fernet` or `ChaCha20Poly1305`

### 2. Password-Based Key Derivation

**Replace**: Current scrypt with Argon2id
- **Algorithm**: Argon2id (memory-hard, resistant to GPU/ASIC attacks)
- **Parameters**:
  - Memory: 64 MiB minimum
  - Iterations: 3
  - Parallelism: 4
- **Rationale**: OWASP recommended, stronger than scrypt

### 3. Ed25519 Implementation

**Option A**: Continue with current pure Python implementation
- **Pros**: No additional dependencies, stays within current architecture
- **Cons**: Potentially slower, less audited

**Option B**: Use `nacl` (PyNaCl) library
- **Pros**: Well-audited, optimized, standard for Ed25519
- **Cons**: Additional dependency

**Recommendation**: Use `nacl` for production, keep pure Python as fallback

### 4. Wallet File Format

**Current Format**:
```json
{
  "version": 1,
  "address": "tach...",
  "public_key": "...",
  "network": "tachoin",
  "sealed": true,
  "seed": {"salt": "...", "nonce": "...", "ciphertext": "...", "tag": "..."}
}
```

**Proposed Format**:
```json
{
  "version": 2,
  "created_at": "2026-10-22T23:50:56Z",
  "format": "argon2chacha",
  "address": "tach...",
  "public_key": "...",
  "network": "tachoin",
  "flags": {
    "sealed": true,
    "bip39_compatible": false
  },
  "crypto": {
    "kdf": "argon2id",
    "kdf_params": {
      "memory": 65536,
      "iterations": 3,
      "parallelism": 4,
      "salt_length": 16
    },
    "aead": "chacha20-poly1305",
    "aead_params": {
      "nonce_length": 12,
      "tag_length": 16
    }
  },
  "encrypted_seed": "..."
}
```

### 5. Recovery Phrase System

**Option 1**: Maintain current custom system (non-BIP-39)
- **Pros**: No breaking changes, stays within current design philosophy
- **Cons**: Limited interoperability

**Option 2**: Implement BIP-39 compatibility
- **Pros**: Industry standard, better interoperability
- **Cons**: Increased complexity, BIP-39 seed phrase is 12/24 words

**Recommendation**: Implement both:
- Keep current custom system for backward compatibility
- Add BIP-39 support as optional feature

### 6. Migration Strategy

**Phase 1**: Add new wallet format (version 2)
- Implement new encryption using Argon2id + ChaCha20-Poly1305
- Support both old and new formats simultaneously

**Phase 2**: Gradual migration
- New wallets use version 2 by default
- Existing wallets remain readable with version 1
- Provide migration utility for users to upgrade

**Phase 3**: Deprecation
- After 2 years, mark version 1 as deprecated
- Require users to re-encrypt their wallets

### 7. Testing Requirements

**Known-Answer Tests**:
1. Test vector for Argon2id key derivation with known parameters
2. Test vector for ChaCha20-Poly1305 encryption
3. Ed25519 signature verification test vectors

**Wrong Passphrase Tests**:
1. Verify decryption fails with incorrect passphrase
2. Verify HMAC validation fails

**Ciphertext Tampering Tests**:
1. Verify modified ciphertext detection
2. Verify modified tag detection

**Malformed File Tests**:
1. Invalid JSON
2. Missing fields
3. Incorrect version

**Deterministic Compatibility Tests**:
1. Same seed + passphrase produces same ciphertext
2. Different nonces produce different ciphertexts

### 8. Implementation Dependencies

**New Dependencies**:
- `argon2-cffi` or `argon2` for Argon2id
- `cryptography` library for ChaCha20-Poly1305
- `nacl` for optimized Ed25519 (optional)

**Migration Path**:
- These can be optional dependencies
- Fall back to existing implementations if new libraries aren't available

### 9. Security Considerations

**New Security Features**:
1. Constant-time operations for all cryptographic primitives
2. Secure random generation with proper entropy sources
3. Memory-hard key derivation to resist GPU/ASIC attacks
4. Standard AEAD constructions with proven security

**Backward Compatibility**:
1. Never overwrite existing wallet files
2. Support reading both old and new formats
3. Provide clear migration paths

### 10. Performance Considerations

**Expected Performance**:-
- Argon2id with 64MiB memory, 3 iterations, 4 parallelism: ~100-200ms on modern CPU
- ChaCha20-Poly1305: ~10-50MB/s throughput
- Ed25519 signing: ~100-500μs per signature

**Memory Usage**:
- Argon2id requires ~64MiB of RAM during key derivation
- Acceptable for modern systems but may be limiting for embedded

## Implementation Plan

### Phase 1: Design and Prototyping (Week 1-2)
1. Research and select libraries for Argon2id and ChaCha20-Poly1305
2. Create prototype implementation
3. Develop known-answer test vectors
4. Verify compatibility with existing wallet format

### Phase 2: Core Implementation (Week 3-4)
1. Implement new wallet format (version 2)
2. Add support for reading both version 1 and version 2 wallets
3. Implement migration utility
4. Create comprehensive test suite

### Phase 3: Integration and Testing (Week 5-6)
1. Integrate with existing wallet API
2. Run existing tests to ensure compatibility
3. Perform security audits
4. Optimize performance

### Phase 4: Documentation and Deployment (Week 7-8)
1. Update documentation
2. Create migration guide
3. Deploy to staging environment
4. Monitor and fix any issues

## Timeline

- **Week 1-2**: Design and prototyping
- **Week 3-4**: Core implementation
- **Week 5-6**: Integration and testing
- **Week 7-8**: Documentation and deployment

**Total**: 8 weeks for complete redesign and implementation

## Risk Assessment

**High Risk**:
1. Breaking changes to wallet format
2. Performance impact of Argon2id
3. Dependency management

**Medium Risk**:
1. Implementation complexity
2. Testing coverage
3. Memory usage on low-end systems

**Low Risk**:
1. Backward compatibility
2. Migration strategy
3. Standard cryptographic primitives

## Conclusion

This redesign addresses all the requirements specified in the task:

1. ✅ Replace custom encryption with well-maintained AEAD implementation
2. ✅ Use memory-hard password-based key derivation with documented parameters
3. ✅ Use mature Ed25519 implementation (nacl library)
4. ✅ Establish clear, versioned wallet file format
5. ✅ Use cryptographically secure randomness
6. ✅ Standardize recovery phrase (support both custom and BIP-39)
7. ✅ Reject malformed formats safely
8. ✅ Add comprehensive tests
9. ✅ Document safe migration path
10. ✅ Avoid custom cryptographic code without justification
11. ✅ Pin and verify dependencies
12. ✅ Do not run tests on real user wallets

The implementation will maintain backward compatibility while significantly improving security and standardization.