# Changelog

All notable changes to Tachoin are documented here. This project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] - 2026-10-22

Compatibility release. **1.0.1 could not start on an up-to-date Tachyon checkout.**

### Fixed

- **Protocol state keys were 20-byte literals in a 256-bit tree.**
  `STATE_KEY_TOTAL_SUPPLY` and friends were written as
  `b"tachoin/total_supply"`, so constructing a node raised
  `ValueError: SMT key must be exactly 32 bytes, got 20` against current Tachyon.
  Every protocol key is now derived through `tachyon.encoding.digest`, which
  guarantees 32 bytes by construction and keeps each key domain-separated.

  This is a **consensus-visible change**: the derived keys produce different
  state roots than the literals did. No block history is affected, because
  1.0.0 and 1.0.1 never produced valid blocks on current Tachyon.

### Why it shipped

The local `tachyon-blockchain` checkout was five commits behind `origin/main`.
Upstream added `SparseMerkleTree._validate_key` in that window, and every test
run - including the "clean clone" checks used to sign off 1.0.0 and 1.0.1 -
cloned the dependency the same stale way, so it always resolved to the old tree.
The regression was invisible until the dependency was refreshed.

### Added

- Four `StateKeyTests` that pin the invariant directly: every protocol key and
  every account key must be exactly 32 bytes, no key family may collide, and a
  freshly built node must satisfy both supply invariants. A literal key of the
  wrong length now fails loudly in the suite rather than only on a modern
  dependency.
- The suite is now 70 tests.

## [1.0.1] - 2026-10-22

Documentation release that also fixes a broken public API entry point.

### Fixed

- **`TachoinClient.stake()` and `TachoinClient.unstake()` raised
  `TransactionError: recipient is not a valid tachoin address` on every call.**
  `_submit` forwarded extra positional arguments after `nonce, slot`, while
  `TachoinTx.build_stake` and `build_unstake` expect `validator` third, so the
  integer nonce was validated as an address and the real validator was
  silently misplaced. Both methods now build their transaction explicitly, in
  the same shape as `transfer`. Reported by the new client-level tests.
- **`Transctions` typo** in the 1.0.0 changelog entry.

### Added

- Seven client-level regression tests covering `stake`, `unstake`, delegation to
  an explicit validator, nonce advancement across every program, rollback of a
  failed client call, and invariants after a mixed client workload. The suite is
  now 66 tests; the 1.0.0 suite only called the transaction builders directly,
  which is why the broken client path shipped.

### Changed

- README rewritten around copy-pasteable examples. Every command, flag, and
  code snippet in it was executed against this release before publishing; two
  documentation errors were caught that way (`create-wallet` has no
  `--validators` flag, and the `run` output listing was incomplete).

## [1.0.0] - 2026-10-22

First official package release.

### Added

- `TachoinWallet`: Ed25519 keys, `tach`-prefixed Base58Check addresses, seed
  derivation from a recovery phrase, and seed files sealed with scrypt plus an
  HMAC-SHA256 keystream and MAC (standard library only, tamper-detecting).
- `TachoinTx`: immutable signed transactions carrying an explicit per-account
  nonce, with JSON and Tachyon `Transaction` bridges.
- Five token programs: `transfer`, `mint`, `burn`, `stake`, `unstake`.
- `TachoinNode`: token state machine with snapshot rollback, per-account nonce
  enforcement, block production on a Tachyon `Ledger`, and validator votes.
- `TokenState`: authoritative key/value state mirrored into a Tachyon sparse
  Merkle tree, so block headers commit to a real state root.
- `TachoinClient`: amount-aware convenience API over a local node.
- `tachoin` CLI: `create-wallet`, `show-wallet`, `status`, `supply`,
  `invariants`, `validators`, `balance`, `transfer`, `mint`, `burn`, `stake`,
  `unstake`, `run`.
- `tachoin._tachyon`: a single dependency resolver covering `TACHYON_PATH`, a
  sibling checkout, and the working directory, with an actionable error.
- 59-test `unittest` regression suite requiring no third-party packages.
- Packaging metadata (`pyproject.toml`, `tachoin` console script), MIT license,
  and `py.typed` marker.

### Fixed

- **Address identity mismatch.** Validators were keyed by Tachyon `tch…`
  addresses while wallets signed with `tach…` addresses, so every transfer from
  a funded account failed with "insufficient balance". All state is now keyed by
  the `tach` address, derived from the same seed.
- **Replayable transactions.** Transactions carried no nonce, so the same signed
  bytes could be applied repeatedly. Nonces are now signed and enforced.
- **Double-applied transactions.** Accepted transactions were executed on
  submission *and* again at block production. Execution now happens exactly
  once, at submission; blocks record the accepted transactions.
- **Double-counted genesis supply.** Genesis wrote each allocation to both the
  balance bucket and the stake bucket, inflating `balances + stakes` to twice
  the circulating supply. Allocations now credit balances only.
- **Wrong supply bucket at genesis.** The 99M reserve was written to the burned
  bucket while the node read the uncirculated bucket, making every `mint` fail
  with "mint exceeds uncirculated supply". The reserve is now genuinely
  uncirculated and burns start at zero.
- **Non-deterministic fee routing.** The transfer fee was credited to the leader
  of the node's *current* slot rather than the transaction's own signed slot, so
  the fee recipient depended on submission timing. Routing is now derived from
  the signed slot.
- **Dependency patch removed.** Tachyon previously had to be patched to add a
  `get` method to its sparse Merkle tree; `TokenState` now owns values itself, so
  the external dependency stays pristine and a fresh clone works unpatched.
- **Resolver short-circuit.** `ensure_tachyon()` reported success when files
  merely existed on disk without inserting the path, leaving `tachyon`
  unimportable. It now verifies the import actually succeeds.

### Security

- Wallet files reject wrong passphrases and modified ciphertext without leaking
  whether the passphrase or the file was wrong.
- Rejected transactions restore the prior state and do not consume a nonce.
- Tampered signatures are rejected before any state change.

[1.0.0]: https://github.com/kp-pc/Tachoin/releases/tag/v1.0.0
[1.0.1]: https://github.com/kp-pc/Tachoin/releases/tag/v1.0.1
[1.0.2]: https://github.com/kp-pc/Tachoin/releases/tag/v1.0.2
