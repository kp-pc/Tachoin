<div align="center">

# ⚡ Tachoin

**A cryptocurrency you can actually reason about.**

Ed25519 wallets · nonce-safe signed transactions · staking · a 100,000,000 TACH supply that provably balances

[![Release](https://img.shields.io/badge/release-v1.0.2-00d4aa?style=for-the-badge)](https://github.com/kp-pc/Tachoin/releases/tag/v1.0.2)
[![Tests](https://img.shields.io/badge/tests-70%20passing-2ea44f?style=for-the-badge)](tests/test_tachoin.py)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)](pyproject.toml)
[![Dependencies](https://img.shields.io/badge/runtime%20deps-none-brightgreen?style=for-the-badge)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)

Built on the [Tachyon](https://github.com/kp-pc/Tachyon-blockchain) blockchain

[Quick start](#-quick-start) · [Why it's different](#-why-tachoin-is-different) · [CLI](#-command-line) · [Python API](#-python-api) · [Architecture](#-architecture)

</div>

---

> **Status: 1.0.2** — reference implementation for development, testing and education.
> Not audited. Do not custody real value with it.

---

## ✨ Why Tachoin is different

Most toy token implementations get the same three things wrong. Tachoin fixes all of them — and every fix has a regression test behind it.

| | The usual bug | What Tachoin does |
|---|---|---|
| 🔑 | State keyed by the chain's native address (`tch…`) while wallets sign with the token address (`tach…`) — so **every transfer from a funded account fails** | Derives both from one seed; all state is keyed by the `tach` address |
| 🔁 | Transactions carry no nonce, so **signed bytes can be replayed forever** | Signed per-account nonce, enforced; replays rejected |
| ⚖️ | Supply is "conserved" in the docs but **never actually checked** | Two invariants asserted after every transaction |

The invariants, checked by the test suite:

```
circulating + uncirculated + burned  ==  total       # supply buckets
balances    + stakes                ==  circulating   # no double-counting
```

That second one caught a real bug during development: genesis credited each allocation to **both** the balance bucket and the stake bucket, silently inflating the token supply to 2×. It's now impossible to reintroduce unnoticed.

---

## 🚀 Quick start

```bash
# 1. Clone the project and its blockchain dependency
git clone https://github.com/kp-pc/Tachoin.git && cd Tachoin
git clone https://github.com/kp-pc/Tachyon-blockchain.git tachyon-blockchain

# 2. Install (provides the `tachoin` command)
pip install -e .

# 3. Run
python -m tachoin invariants
python -m tachoin run --blocks 20 --txs-per-block 5
```

```console
$ python -m tachoin run --blocks 5 --txs-per-block 2
Simulating 5 blocks x 2 transfers on 4 validators

Finished 5 blocks in 0.067s
  final slot        : 5
  finalized slot    : 5
  total blocks      : 6
  total supply      : 100000000.000000 TACH
  circulating       : 1000000.000000 TACH
  uncirculated      : 99000000.000000 TACH
  burned            : 0.000000 TACH
  supply invariant  : True
  balance invariant : True
  throughput        : 74.4 blocks/s, 148.7 transfers/s
  latest block      : 57a721980dabe540...
```

> **Tachyon isn't on PyPI.** It's resolved at runtime from, in order: an importable `tachyon` → `$TACHYON_PATH` → `./tachyon-blockchain` → `./tachyon`.
> If none exist, importing `tachoin` raises an `ImportError` telling you exactly which clone to make.

**Requirements:** Python 3.10+ · zero third-party runtime dependencies

---

## 🔐 Wallets

```bash
python -m tachoin create-wallet --save wallet.json --passphrase 'correct horse battery staple'
python -m tachoin show-wallet wallet.json
```

Seeds are sealed with **scrypt** (`n=2^14, r=8, p=1`) plus an **HMAC-SHA256** keystream and MAC — standard library only. Wrong passphrases and tampered ciphertext are both rejected, without revealing which was wrong.

Omit `--passphrase` and the file is written with `"sealed": false`, so the unprotected state is **explicit rather than implied**.

---

## 💻 Command line

| Command | What it does |
|---|---|
| `create-wallet` | Generate a wallet; `--save PATH` and `--passphrase` to persist |
| `show-wallet` | Print a wallet file's public data |
| `status` | Node status: slot, blocks, supply, state root |
| `supply` | Total / circulating / uncirculated / burned |
| `invariants` | Check both conservation invariants |
| `validators` | List validator addresses |
| `balance ADDRESS` | Balance of any address |
| `transfer TO AMOUNT` | Send TACH |
| `mint AMOUNT` | Validators only — mints from the reserve |
| `burn AMOUNT` | Permanently destroy TACH |
| `stake AMOUNT [VALIDATOR]` | Lock TACH toward a validator |
| `unstake AMOUNT [VALIDATOR]` | Return stake to balance |
| `run --blocks N` | Block production simulation with throughput |

Node commands (`status`, `supply`, `invariants`, `validators`, `balance`, `transfer`, `mint`, `burn`, `stake`, `unstake`, `run`) accept `--validators N` and `--seeds HEX…` for reproducible runs. Wallet commands take neither.

---

## 🐍 Python API

**High level** — amounts as human-readable strings:

```python
from tachoin.client import TachoinClient

client = TachoinClient(num_validators=4)
sender, recipient = client.validator_wallets()[:2]

print(client.transfer(sender, recipient.address, "10.5"))
# {'success': True, 'tx_hash': '…', 'nonce': 0, 'new_balance': '249989.499999 TACH', 'error': None}

client.mint(sender, "1000")    # validators only
client.burn(sender, "25")
client.stake(sender, "100")
client.supply()
client.status()
```

**Low level** — explicit nonces and slot control:

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
    node.get_nonce(wallet.address),  # explicit nonce
    node.get_current_slot() + 1,     # fee routes to this slot's leader
)

result = node.submit_transaction(tx)
print(result.success, format_tach(node.get_balance(wallet.address)))
```

---

## 💰 Tokenomics

| Parameter | Value |
|---|---|
| Symbol / decimals | **TACH** / 18 |
| Total supply | **100,000,000 TACH** |
| Genesis circulating | 1,000,000 TACH (split across validators) |
| Uncirculated reserve | 99,000,000 TACH (mintable by validators) |
| Burned at genesis | 0 TACH |
| Transfer fee | 1,000 base units (0.000000000000001 TACH) |
| Slot time | 400 ms |

---

## ⚙️ Programs

| Program | Who | Effect |
|---|---|---|
| `transfer` | anyone | Moves TACH; the fee credits the leader of the transaction's **signed slot** |
| `mint` | validators | Moves TACH from uncirculated into circulating |
| `burn` | anyone | Destroys TACH, growing the burned bucket |
| `stake` | anyone | Moves balance into stake for a known validator |
| `unstake` | anyone | Returns stake to balance |

Rejected — with the prior state restored and **no nonce consumed**: self-transfers, non-positive amounts, unknown validators, insufficient balance/stake, replayed or out-of-order nonces, and tampered signatures.

---

## 🏗 Architecture

```
tachoin/
├── _tachyon.py      single place that resolves the Tachyon dependency
├── config.py        token constants and every SMT state key
├── state.py         TokenState — owns values, mirrors writes into a Tachyon SMT
├── wallet.py        Ed25519 keys, tach addresses, scrypt-sealed seed files
├── transaction.py   TachoinTx — signed, nonce-carrying, JSON + Tachyon bridges
├── genesis.py       genesis block and initial supply/balance allocation
├── node.py          state machine, invariants, block production
├── client.py        amount-aware convenience API
└── __main__.py      CLI
tests/               70-test stdlib unittest suite
```

**State** lives in `TokenState`: the authoritative key/value map, mirrored into a Tachyon `SparseMerkleTree` so block headers commit to a real Merkle root. Tachyon is an unreleased external dependency and stays **unmodified** — no vendored patches.

**Execution** happens exactly once, at submission. The next block includes those transactions *without re-applying them*, so a block is a record of completed work rather than a second execution.

---

## ✅ Tests

```bash
python -m unittest discover -s tests -t . -v
```

**70 tests, standard library only** — no pytest required. Coverage: address/signature identity, wallet sealing and tamper detection, amount parsing, genesis allocation, nonce replay and out-of-order rejection, failed-transaction rollback, mint/burn/stake/unstake, supply and balance conservation, block inclusion, state-root changes, and the client API for every program.

---

## 🛡 Security notes

The honest list:

- The wallet format uses scrypt + HMAC-SHA256 built from stdlib primitives. **Not audited.** For meaningful value, use a reviewed keystore.
- Ed25519 comes from Tachyon and is pure Python — **not constant-time.** Avoid it where side-channel resistance matters.
- `TachoinNode` is an **in-process simulation harness**. It produces blocks and votes locally; it is not a networked consensus node.

---

## 📄 License

MIT — see [LICENSE](LICENSE).

<div align="center">

**[⬆ back to top](#-tachoin)**

</div>
