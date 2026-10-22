# Changelog

All notable changes to Tachoin are documented here. This project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **Replayable transactions.** Transctions carried no nonce, so the same signed
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
