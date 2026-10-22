# ⚡ Tachoin

A cryptocurrency built on the **Tachyon** high-performance blockchain.

Tachoin (TACH) is a native token with transfer, mint, burn, staking, and unstaking functionality that runs on Tachyon's pipelined, stake-weighted BFT consensus engine.

---

## Features

- **Ed25519 Signatures**: RFC 8032 compliant, pure Python (no dependencies)
- **100M Total Supply**: Fixed cap with genesis reward pool
- **Transfer**: Move TACH between addresses with a configurable fee
- **Mint**: Validators can mint new TACH within the supply cap
- **Burn**: Permanently destroy TACH to reduce circulating supply
- **Stake / Unstake**: Lock TACH with validators for consensus participation
- **Block Production**: Inherited Tachyon 6-stage pipeline with optimistic parallel execution
- **Sparse Merkle Tree State**: Compact state commitments for balances and supply

## Token Parameters

| Parameter | Value |
|-----------|-------|
| Symbol | TACH |
| Decimals | 18 |
| Total Supply | 100,000,000 TACH |
| Genesis Pool | 1,000,000 TACH |
| Transfer Fee | 0.000001 TACH |
| Min Stake | 100 TACH |
| Staking APR | 5% |
| Slot Time | 400 ms |

## Prerequisites

```bash
# Clone Tachyon (required dependency)
git clone https://github.com/kp-pc/Tachyon-blockchain.git tachyon-blockchain
```

Python 3.10+, no external dependencies.

## Quick Start

```bash
# Create a wallet
python -m tachoin create-wallet

# Check network status
python -m tachoin status

# Check supply
python -m tachoin supply

# Transfer TACH
python -m tachoin transfer <address> 10

# Run block production simulation
python -m tachoin run --blocks 20 --txs-per-block 5
```

## Python API

```python
from tachoin.client import TachoinClient
from tachoin.node import _keypair_to_wallet

client = TachoinClient(num_validators=4)
node = client.get_node()

# Get a validator's wallet
wallet = _keypair_to_wallet(node._validators[0])

# Transfer
result = client.transfer(wallet, "tach1...", "50")
print(result["success"], result["tx_hash"])

# Burn
result = client.burn(wallet, "25")

# Stake
result = client.stake(wallet, "100", node._validators[1].address)

# Supply
print(client.supply())

# Status
print(client.status())
```

## Project Structure

```
tachoin/
├── __init__.py       # Package init
├── config.py         # Token constants & state key helpers
├── wallet.py         # TachoinWallet (Ed25519, 'tach' addresses)
├── transaction.py    # TachoinTx (transfer, mint, burn, stake, unstake)
├── genesis.py        # Genesis block & initial state
├── node.py           # TachoinNode (core state machine & block production)
├── client.py         # High-level TachoinClient API
└── __main__.py       # CLI entry point
tachyon-blockchain/   # (cloned dependency)
├── tachyon/
│   ├── chain.py      # Ledger, Block, Transaction, State
│   ├── crypto.py     # Ed25519, Base58
│   ├── smt.py        # Sparse Merkle Tree
│   ├── mempool.py    # Transaction pool
│   ├── election.py   # Leader rotation
│   └── ...
```

## Security Note

This is an educational implementation. Do not use for production financial value transfer.
