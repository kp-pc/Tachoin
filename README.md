# Tachoin (TACH)

A cryptocurrency implementation built on the [Tachyon](https://github.com/kp-pc/Tachyon-blockchain) blockchain: Ed25519 wallets, nonce-safe signed transactions, staking, and a conserved 100M supply committed to a sparse Merkle tree.

**Status: 1.0.0** — reference implementation for development, testing and education. It is not audited and must not custody real value.

---

## Why the design is interesting

Most toy token implementations get three things wrong. Tachoin addresses all three, and each is covered by a regression test.

**1. Address identity must match signature identity.**
Tachyon uses `tch…` addresses; Tachoin uses `tach…`. If state is keyed by one form while wallets sign with the other, every transfer fails with "insufficient balance" against a funded account. Tachoin derives *both* from one seed and keys all state by the `tach` address:

```python
>>> from tachyon.crypto import KeyPair
>>> from tachoin.wallet import TachoinWallet
>>> keypair = KeyPair.generate()
>>> keypair.address.startswith("tch")          # Tachyon's native form
True
>>> TachoinWallet(seed=keypair.seed).address.startswith("tach")  # what TACH state uses
True
```

**2. Transactions must not be replayable.**
Every transaction carries a signed `nonce`, and the node rejects anything that is not the account's next expected value:

```python
>>> result = node.submit_transaction(tx)        # accepted, nonce 0 -> 1
>>> node.submit_transaction(tx)                 # same bytes again
TachoinResult(success=False, error='invalid nonce: expected 1, got 0', ...)
```

**3. Supply must actually balance.**
Two invariants hold after every accepted transaction and are asserted throughout the suite:

- `circulating + uncirculated + burned == total`
- `balances + stakes == circulating`

The second one catches a subtle bug: crediting a genesis allocation to *both* the balance bucket *and* the stake bucket double-counts the same tokens. Genesis credits balances only; consensus stake lives on the Tachyon ledger.

---

## Install

Tachyon is not published on PyPI, so it is resolved at runtime rather than declared as a dependency.

```bash
git clone https://github.com/kp-pc/Techoin.git
cd Techoin
git clone https://github.com/kp-pc/Tachyon-blockchain.git tachyon-blockchain

pip install -e .          # provides the `tachoin` command
```

Resolution order for the dependency: already-importable `tachyon` → `$TACHYON_PATH` → `./tachyon-blockchain` → `./tachyon`. If none apply, importing `tachoin` raises an `ImportError` telling you exactly which clone to make. Python 3.10+; no third-party runtime dependencies.

## Quick start

```bash
python -m tachoin --version
python -m tachoin supply
python -m tachoin invariants
python -m tachoin run --blocks 20 --txs-per-block 5
```

```
$ python -m tachoin run --blocks 5 --txs-per-block 2
Simulating 5 blocks x 2 transfers on 4 validators

Finished 5 blocks in 0.061s
  final slot        : 5
  total supply      : 100000000.000000 TACH
  circulating       : 1000000.000000 TACH
  uncirculated      : 99000000.000000 TACH
  burned            : 0.000000 TACH
  supply invariant  : True
  balance invariant : True
  throughput        : 81.4 blocks/s, 162.8 transfers/s
```

### Wallets

```bash
python -m tachoin create-wallet --save wallet.json --passphrase 'correct horse battery staple'
python -m tachoin show-wallet wallet.json
```

A passphrase seals the seed with scrypt (`n=2^14, r=8, p=1`) plus an HMAC-SHA256 keystream and MAC, using only the standard library. Wrong passphrases and tampered ciphertext are both rejected. Without `--passphrase` the file is written with `"sealed": false` — the unprotected state is explicit rather than implied.

## Python API

```python
from tachoin.client import TachoinClient

client = TachoinClient(num_validators=4)
sender, recipient = client.validator_wallets()[:2]

print(client.transfer(sender, recipient.address, "10.5"))
# {'success': True, 'tx_hash': '...', 'nonce': 0, 'new_balance': '249989.499999 TACH', 'error': None}

print(client.mint(sender, "1000"))       # validators only
print(client.burn(sender, "25"))
print(client.stake(sender, "100"))
print(client.supply())
print(client.status())
```

Low-level control, with explicit nonces:

```python
from tachoin.node import TachoinNode, format_tach, parse_tach
from tachoin.transaction import TachoinTx
from tachyon.crypto import KeyPair

node = TachoinNode([KeyPair.generate() for _ in range(4)])
wallet = node.wallet_for(node.validator_addresses()[0])

tx = TachoinTx.build_transfer(
    wallet,
    node.validator_addresses()[1],
    parse_tach("5"),
    node.get_nonce(wallet.address),   # explicit nonce
    node.get_current_slot() + 1,      # fee routes to this slot's leader
)
result = node.submit_transaction(tx)
print(result.success, format_tach(node.get_balance(wallet.address)))
```

## Token parameters

| Parameter | Value |
|---|---|
| Symbol / decimals | TACH / 18 |
| Total supply | 100,000,000 TACH |
| Genesis circulating | 1,000,000 TACH (split across validators) |
| Uncirculated reserve | 99,000,000 TACH (mintable by validators) |
| Burned at genesis | 0 |
| Transfer fee | 1,000 base units (0.000000000000001 TACH) |
| Slot time | 400 ms |

## Programs

| Program | Who | Effect |
|---|---|---|
| `transfer` | anyone | Moves TACH; fee credits the leader of the transaction's signed slot |
| `mint` | validators | Moves TACH from uncirculated into circulating |
| `burn` | anyone | Destroys TACH, growing the burned bucket |
| `stake` | anyone | Moves balance into stake for a known validator |
| `unstake` | anyone | Returns stake to balance |

Self-transfers, non-positive amounts, unknown validators, insufficient balances and replayed nonces are all rejected, and a rejected transaction restores the pre-transaction state without consuming a nonce.

## Architecture

```
tachoin/
├── _tachyon.py      # single place that resolves the Tachyon dependency
├── config.py        # token constants and every SMT state key
├── state.py         # TokenState: owns values, mirrors writes into a Tachyon SMT
├── wallet.py        # Ed25519 keys, tach addresses, scrypt-sealed seed files
├── transaction.py   # TachoinTx: signed, nonce-carrying, JSON + Tachyon bridges
├── genesis.py       # genesis block and initial supply/balance allocation
├── node.py          # state machine, invariants, block production
├── client.py        # amount-aware convenience API
└── __main__.py      # CLI
```

State lives in `TokenState`, which keeps the authoritative key/value map and mirrors each write into a Tachyon `SparseMerkleTree` so block headers commit to a real Merkle root. Tachyon is an unreleased external dependency and is kept unmodified — no patching of a vendored tree is required.

Transactions are applied exactly once, at submission. The next block includes the accepted transactions without re-applying them, so a block is a record of completed work rather than a second execution.

## Tests

```bash
python -m unittest discover -s tests -t . -v
```

59 tests, standard library only (no pytest required). They cover address/signature identity, wallet sealing and tamper detection, amount parsing, genesis allocation, nonce replay and out-of-order rejection, failed-transaction rollback, mint/burn/stake/unstake, supply and balance conservation, block inclusion and state-root changes.

## Security notes

- The wallet file format uses scrypt plus HMAC-SHA256, built from stdlib primitives. It is not audited; for meaningful value use a reviewed keystore instead.
- The bundled Ed25519 implementation comes from Tachyon and is pure Python — not constant-time. Do not use it where side-channel resistance matters.
- `TachoinNode` is an in-process simulation harness. It produces blocks and votes locally; it is not a networked consensus node.

## License

MIT — see [LICENSE](LICENSE).
