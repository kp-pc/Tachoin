# Tachoin-Coin Threat Model

## Overview

This document outlines the security threats, attack surfaces, and mitigation strategies for Tachoin-Coin, a reference cryptocurrency implementation for development, testing, and education purposes.

## Deployment Modes

### Development Mode
- **Purpose**: Educational and testing purposes
- **Security Requirements**: Low operational security
- **Risk Tolerance**: High - prone to user error
- **Mitigations**: Documentation warnings, sandboxing

### Simulation Mode
- **Purpose**: Network simulation, research
- **Security Requirements**: Medium operational security
- **Risk Tolerance**: Medium - limited exposure
- **Mitigations**: Validator node control, network isolation

### Educational Mode
- **Purpose**: Teaching cryptocurrency concepts
- **Security Requirements**: Minimal operational security
- **Risk Tolerance**: Very High - entertainment focus
- **Mitigations**: Emphasis on learning over security

## Threat Actors

### 1. Malicious Validators
- **Motivation**: Disrupt consensus, manipulate state
- **Capabilities**: Block production, validator voting
- **Target**: State integrity, consensus rules
- **Mitigation**: Multi-party consensus, equivocation detection

### 2. Transaction Replay attackers
- **Motivation**: Fee evasion, double-spend
- **Capabilities**: Transaction signing, submission
- **Target**: Nonce enforcement, slot freshness
- **Mitigation**: Per-account nonces, slot freshness windows

### 3. Wallet compromise
- **Motivation**: Private key extraction, fund theft
- **Capabilities**: Wallet file decryption, seed recovery
- **Target**: Wallet storage, seed phrase protection
- **Mitigation**: Strong encryption, passphrase protection

### 4. Protocol manipulation
- **Motivation**: Supply inflation, balance theft
- **Capabilities**: State observation, protocol rule exploitation
- **Target**: Supply conservation, balance invariants
- **Mitigation**: Invariant checking, atomic state updates

### 5. Network disruption
- **Motivation**: Denial of service, network partition
- **Capabilities**: Block withholding, transaction flooding
- **Target**: Network availability, mempool management
- **Mitigation**: Mempool bounds, network simulations

## Attack Vectors

### Protocol-Level Threats

#### 1. Nonce Reuse and Replay Attacks
- **Description**: Reusing signed transaction bytes to execute multiple transactions
- **Impact**: Double-spend, unauthorized transfers
- **Probability**: High without proper nonce enforcement
- **Mitigation**: Per-account monotonic nonces, replay detection

#### 2. Fee Evasion Attacks
- **Description**: Crafting transactions with insufficient fees to skip validator payouts
- **Impact**: Validator starvation, network degradation
- **Probability**: High without fee minimum enforcement
- **Mitigation**: Minimum fee enforcement, slot-based fee allocation

#### 3. State Manipulation
- **Description**: Exploiting race conditions in state updates
- **Impact**: Supply inflation, balance corruption
- **Probability**: Medium without atomic updates
- **Mitigation**: Atomic state updates, invariant checking

#### 4. Slot Freshness Exploitation
- **Description**: Using stale transactions with old fee values
- **Impact**: Fee circumvention, validator payout manipulation
- **Probability**: Medium without freshness windows
- **Mitigation**: Slot freshness windows, transaction expiration

### Implementation-Level Threats

#### 1. Cryptographic Weaknesses
- **Description**: Implementation flaws in Ed25519 or encryption
- **Impact**: Signature forgery, wallet compromise
- **Probability**: Low with standard libraries
- **Mitigation**: Standard cryptographic libraries, regular audits

#### 2. Input Validation Failures
- **Description**: Malformed inputs causing crashes or errors
- **Impact**: Denial of service, information disclosure
- **Probability**: Medium without proper validation
- **Mitigation**: Comprehensive input validation, error normalization

#### 3. Memory Corruption
- **Description**: Buffer overflows or memory safety issues
- **Impact**: Remote code execution, system compromise
- **Probability**: Low (Python environment)
- **Mitigation**: Safe Python practices, bounds checking

### Network-Level Threats

#### 1. Transaction Flooding
- **Description**: Overwhelming mempool with spam transactions
- **Impact**: Memory exhaustion, network degradation
- **Probability**: Medium without mempool limits
- **Mitigation**: Mempool size limits, rate limiting

#### 2. Block Withholding
- **Description**: Validator withholding blocks to disrupt consensus
- **Impact**: Network partitions, liveness failure
- **Probability**: Low in simulation mode
- **Mitigation**: Reward mechanisms, liveness detection

## Security Controls

### Cryptographic Controls

#### 1. Wallet Protection
- **Algorithm**: Scrypt + HMAC-SHA256 encryption
- **Key Derivation**: Argon2id proposal in progress
- **Strength**: Currently adequate, proposed upgrade to ChaCha20-Poly1305
- **Status**: Meets requirements for educational use

#### 2. Transaction Signing
- **Algorithm**: Ed25519 (from Tachyon)
- **Strength**: Pure Python implementation, not constant-time
- **Status**: Adequate for non-production use

### Protocol Controls

#### 1. Supply Conservation
- **Invariants**: Two mathematical invariants enforced
- **Verification**: Checked after every transaction
- **Strength**: Provably maintains supply integrity
- **Status**: Robust and well-tested

#### 2. Nonce Enforcement
- **Mechanism**: Per-account monotonic nonces
- **Strength**: Prevents replay, enforces ordering
- **Status**: Secure and tested

### Operational Controls

#### 1. Input Validation
- **Scope**: All transaction inputs, wallet files, network messages
- **Method**: Schema validation, type checking, bounds verification
- **Coverage**: Comprehensive with regression tests
- **Status**: Strong

#### 2. Error Handling
- **Principle**: Normalized error messages, no information leakage
- **Scope**: All user-facing error responses
- **Strength**: Prevents timing attacks, information disclosure
- **Status**: Robust

## Known Limitations

### Cryptographic Limitations
1. **Ed25519 Implementation**: Pure Python, not constant-time
   - Impact: Vulnerable to timing attacks in high-security contexts
   - Acceptance: Suitable for educational purposes only

2. **Wallet Encryption**: Custom construction not standard AEAD
   - Impact: May have undiscovered vulnerabilities
   - Status: Proposed redesign to ChaCha20-Poly1305 + Argon2id

### Protocol Limitations
1. **Simulation Environment**: Not a production consensus node
   - Impact: No real network security guarantees
   - Mitigation: Clear documentation and warnings

2. **Trusted Validators**: All validators controlled by user
   - Impact: No protection against malicious validators
   - Mitigation: Simulation assumption documented

### Operational Limitations
1. **No Independent Audit**: No formal security verification
   - Impact: Unknown security posture for production use
   - Status: Clearly documented in all materials

2. **Educational Focus**: Optimized for learning, not security
   - Impact: Security features may be overridden for educational value
   - Mitigation: Clear usage guidance

## Deployment Recommendations

### For Development Use
1. **Use Simulation Mode**: Understand the protocol before deploying elsewhere
2. **Read All Documentation**: Multiple warnings about security limitations
3. **Use Strong Passwords**: Protect wallet files with strong passphrases
4. **Never Custodiate Real Value**: Explicit warning in all documentation

### For Testing
1. **Isolated Environment**: Run in sandboxed, disposable environments
2. **Test Coverage**: Use full test suite before any changes
3. **Version Pinning**: Always test against specific Tachyon versions
4. **Regular Updates**: Apply security fixes promptly

### For Educational Use
1. **Emphasis on Learning**: Focus on protocol understanding over security
2. **Controlled Environments**: Use development mode with clear limitations
3. **Documentation Study**: Read the security limitations before use
4. **No Production Deployment**: Never use for real value storage

## Future Security Improvements

### Phase 1 (Recommended)
1. Implement cryptographic redesign proposal (ChaCha20-Poly1305 + Argon2id)
2. Add standard Ed25519 library (PyNaCl)
3. Improve wallet file format versioning
4. Add comprehensive security testing

### Phase 2 (Long-term)
1. Independent security audit
2. Formal verification of critical invariants
3. Production-grade security hardening
4. Network consensus implementation

## Conclusion

Tachoin-Coin provides a robust educational and testing environment for understanding cryptocurrency protocols. It has addressed critical security vulnerabilities through comprehensive regression testing and proper protocol design. However, it is explicitly **NOT** intended for production use with real value due to the following reasons:

1. No independent security audit
2. Pure Python cryptographic implementations
3. Custom (non-standard) cryptographic constructions
4. Simulation environment, not production consensus
5. Educational focus over production hardening

**Recommendation**: Use Tachoin-Coin for development, testing, and education only. Never custody real cryptocurrency value with this implementation.