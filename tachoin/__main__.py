"""Tachoin CLI entry point.

Usage:
    python -m tachoin create-wallet
    python -m tachoin status
    python -m tachoin balance <address>
    python -m tachoin transfer <to> <amount>
    python -m tachoin mint <amount>          # validator only
    python -m tachoin burn <amount>
    python -m tachoin stake <amount> [validator]
    python -m tachoin unstake <amount> [validator]
    python -m tachoin supply
    python -m tachoin run [--blocks N] [--txs-per-block M]
"""

from __future__ import annotations

import argparse
import json
import sys
import os

# Add Tachyon to path
_TACHYON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tachyon-blockchain")
if _TACHYON_PATH not in sys.path:
    sys.path.insert(0, _TACHYON_PATH)

from tachyon.crypto import KeyPair

from .client import TachoinClient
from .wallet import TachoinWallet
from .config import TOKEN_DECIMALS, GENESIS_REWARD_POOL
import time


def cmd_create_wallet(args: argparse.Namespace) -> None:
    """Create a new tachoin wallet and display details."""
    wallet = TachoinWallet.generate()
    print("New Tachoin wallet created:\n")
    print(f"  Address    : {wallet.address}")
    print(f"  Public Key : {wallet.public_key_hex}")
    print(f"  Seed (hex) : {wallet.seed_hex}")
    print()
    print("WARNING: Save your seed securely. Anyone with the seed can access your funds.")
    print("Use 'save' option to persist the wallet to disk.")


def cmd_save_wallet(args: argparse.Namespace) -> None:
    """Save wallet to file."""
    wallet = TachoinWallet.generate()
    path = args.path or "wallet.json"
    passphrase = args.passphrase
    TachoinWallet.save(path, wallet, passphrase)
    print(f"Wallet saved to {path}")
    print(f"  Address: {wallet.address}")


def cmd_load_wallet(args: argparse.Namespace) -> TachoinWallet:
    """Load wallet from file."""
    path = args.path or "wallet.json"
    passphrase = args.passphrase
    return TachoinWallet.load(path, passphrase)


def _get_client() -> TachoinClient:
    return TachoinClient(num_validators=4)


def cmd_status(args: argparse.Namespace) -> None:
    client = _get_client()
    status = client.status()
    print(json.dumps(status, indent=2))


def cmd_balance(args: argparse.Namespace) -> None:
    client = _get_client()
    result = client.balance(args.address)
    print(f"Balance: {result['balance']}")
    print(f"Address: {result['address']}")


def cmd_supply(args: argparse.Namespace) -> None:
    client = _get_client()
    s = client.supply()
    print(f"Total supply     : {s['total']}")
    print(f"Circulating supply: {s['circulating']}")
    print(f"Burned supply    : {s['burned']}")


def cmd_transfer(args: argparse.Namespace) -> None:
    client = _get_client()
    # Use validator 0's wallet as sender
    validators = client.get_validator_addresses()
    sender_wallet = TachoinWallet.generate()  # In production, this would be loaded from disk
    # For simulation, we use the validator's wallet
    from .node import _keypair_to_wallet
    # We need access to the validators - let's use a different approach
    node = client.get_node()
    validators_kp = node._validators
    sender = _keypair_to_wallet(validators_kp[0])

    result = client.transfer(sender, args.to, args.amount)
    if result["success"]:
        print(f"Transfer successful!")
        print(f"  Tx hash     : {result['tx_hash']}")
        print(f"  New balance : {result['new_balance']}")
    else:
        print(f"Transfer failed: {result['error']}")
        sys.exit(1)


def cmd_mint(args: argparse.Namespace) -> None:
    client = _get_client()
    node = client.get_node()
    from .node import _keypair_to_wallet
    validators_kp = node._validators
    sender = _keypair_to_wallet(validators_kp[0])

    result = client.mint(sender, args.amount)
    if result["success"]:
        print(f"Mint successful! Tx hash: {result['tx_hash']}")
    else:
        print(f"Mint failed: {result['error']}")
        sys.exit(1)


def cmd_burn(args: argparse.Namespace) -> None:
    client = _get_client()
    node = client.get_node()
    from .node import _keypair_to_wallet
    validators_kp = node._validators
    sender = _keypair_to_wallet(validators_kp[0])

    result = client.burn(sender, args.amount)
    if result["success"]:
        print(f"Burn successful! Tx hash: {result['tx_hash']}")
    else:
        print(f"Burn failed: {result['error']}")
        sys.exit(1)


def cmd_stake(args: argparse.Namespace) -> None:
    client = _get_client()
    node = client.get_node()
    from .node import _keypair_to_wallet
    validators_kp = node._validators
    sender = _keypair_to_wallet(validators_kp[0])

    validator = args.validator or validators_kp[0].address
    result = client.stake(sender, args.amount, validator)
    if result["success"]:
        print(f"Stake successful! Tx hash: {result['tx_hash']}")
    else:
        print(f"Stake failed: {result['error']}")
        sys.exit(1)


def cmd_unstake(args: argparse.Namespace) -> None:
    client = _get_client()
    node = client.get_node()
    from .node import _keypair_to_wallet
    validators_kp = node._validators
    sender = _keypair_to_wallet(validators_kp[0])

    validator = args.validator or validators_kp[0].address
    result = client.unstake(sender, args.amount, validator)
    if result["success"]:
        print(f"Unstake successful! Tx hash: {result['tx_hash']}")
    else:
        print(f"Unstake failed: {result['error']}")
        sys.exit(1)


def cmd_run(args: argparse.Namespace) -> None:
    """Run a simulation: produce blocks with transfers."""
    client = _get_client()
    node = client.get_node()

    blocks = args.blocks
    txs_per_block = args.txs_per_block

    print(f"Running Tachoin simulation: {blocks} blocks x {txs_per_block} txs/block")
    print(f"Network: {node.status()['network']}  Token: {node.status()['token']}")
    print()

    t_start = time.perf_counter()
    final_slot = node.produce_blocks(blocks, txs_per_block)
    t_elapsed = time.perf_counter() - t_start

    status = node.status()
    print(f"Simulation complete in {t_elapsed:.3f}s")
    print(f"  Final slot       : {final_slot}")
    print(f"  Total blocks     : {status['total_blocks']}")
    print(f"  Finalized slot   : {status['finalized_slot']}")
    print(f"  Total supply     : {status['total_supply']}")
    print(f"  Circulating      : {status['circulating_supply']}")
    print(f"  Burned           : {status['burned_supply']}")
    print(f"  Txs/sec          : {round(blocks * txs_per_block / t_elapsed, 2) if t_elapsed > 0 else 0}")
    print(f"  Blocks/sec       : {round(blocks / t_elapsed, 2) if t_elapsed > 0 else 0}")
    print(f"  Latest block hash: {status['latest_block_hash'][:16]}...")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tachoin - a cryptocurrency built on the Tachyon blockchain",
        prog="tachoin",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # create-wallet
    sub.add_parser("create-wallet", help="Create a new Tachoin wallet")

    # save-wallet
    p = sub.add_parser("save-wallet", help="Save a new wallet to file")
    p.add_argument("--path", default="wallet.json", help="Output file path")
    p.add_argument("--passphrase", default=None, help="Passphrase for encryption")

    # status
    sub.add_parser("status", help="Show node status")

    # balance
    p = sub.add_parser("balance", help="Show balance for an address")
    p.add_argument("address", type=str, help="Tachoin address")

    # supply
    sub.add_parser("supply", help="Show token supply statistics")

    # transfer
    p = sub.add_parser("transfer", help="Transfer TACH to an address")
    p.add_argument("to", type=str, help="Recipient address")
    p.add_argument("amount", type=str, help="Amount in TACH, e.g. '50' or '50.123456'")

    # mint
    p = sub.add_parser("mint", help="Mint TACH (validator only)")
    p.add_argument("amount", type=str, help="Amount to mint")

    # burn
    p = sub.add_parser("burn", help="Burn TACH")
    p.add_argument("amount", type=str, help="Amount to burn")

    # stake
    p = sub.add_parser("stake", help="Stake TACH")
    p.add_argument("amount", type=str, help="Amount to stake")
    p.add_argument("validator", type=str, nargs="?", default=None, help="Validator address")

    # unstake
    p = sub.add_parser("unstake", help="Unstake TACH")
    p.add_argument("amount", type=str, help="Amount to unstake")
    p.add_argument("validator", type=str, nargs="?", default=None, help="Validator address")

    # run
    p = sub.add_parser("run", help="Run a block production simulation")
    p.add_argument("--blocks", type=int, default=10, help="Number of blocks to produce")
    p.add_argument("--txs-per-block", type=int, default=3, help="Transactions per block")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    commands = {
        "create-wallet": cmd_create_wallet,
        "save-wallet": cmd_save_wallet,
        "status": cmd_status,
        "balance": cmd_balance,
        "supply": cmd_supply,
        "transfer": cmd_transfer,
        "mint": cmd_mint,
        "burn": cmd_burn,
        "stake": cmd_stake,
        "unstake": cmd_unstake,
        "run": cmd_run,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
