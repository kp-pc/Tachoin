"""Tachoin command line interface.

Examples::

    python -m tachoin create-wallet --save wallet.json
    python -m tachoin status
    python -m tachoin supply
    python -m tachoin transfer <address> 10
    python -m tachoin run --blocks 20 --txs-per-block 5

Every command operates on an in-process simulation node with a freshly
generated validator set, unless validator seeds are supplied with
``--seeds``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional

from . import __version__
from .client import TachoinClient
from .config import TOKEN_SYMBOL
from .wallet import TachoinWallet


def _client(args: argparse.Namespace) -> TachoinClient:
    """Build a client from ``--seeds`` or a fresh validator set."""
    seeds: Optional[List[str]] = getattr(args, "seeds", None)
    if seeds:
        return TachoinClient.from_seeds(seeds)
    return TachoinClient(num_validators=getattr(args, "validators", 4))


def _print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


# ---- Wallet commands --------------------------------------------------


def cmd_create_wallet(args: argparse.Namespace) -> None:
    wallet = TachoinWallet.generate()
    print(f"New {TOKEN_SYMBOL} wallet\n")
    print(f"  Address    : {wallet.address}")
    print(f"  Public key : {wallet.public_key_hex}")
    print(f"  Seed (hex) : {wallet.seed_hex}")
    print()
    print("Anyone holding the seed can spend this wallet's funds.")

    if args.save:
        path = wallet.save(args.save, args.passphrase)
        protection = "sealed with a passphrase" if args.passphrase else "UNENCRYPTED"
        print(f"Saved to {path} ({protection}).")


def cmd_show_wallet(args: argparse.Namespace) -> None:
    try:
        wallet = TachoinWallet.load(args.path, args.passphrase)
    except (OSError, ValueError) as exc:
        _fail(str(exc))
    _print_json(wallet.to_dict())


# ---- Queries ----------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> None:
    _print_json(_client(args).status())


def cmd_supply(args: argparse.Namespace) -> None:
    _print_json(_client(args).supply())


def cmd_balance(args: argparse.Namespace) -> None:
    client = _client(args)
    _print_json(client.balance(args.address))


def cmd_validators(args: argparse.Namespace) -> None:
    client = _client(args)
    _print_json(
        {
            "count": len(client.validator_addresses()),
            "addresses": client.validator_addresses(),
        }
    )


# ---- Transactions -----------------------------------------------------


def _sender(args: argparse.Namespace, client: TachoinClient) -> TachoinWallet:
    """Resolve the sending wallet from ``--from`` or validator 0."""
    wallets = client.validator_wallets()
    if args.sender:
        for wallet in wallets:
            if wallet.address == args.sender:
                return wallet
        _fail("sender is not a validator wallet; use a seed-backed wallet")
    return wallets[args.sender_index]


def _report(result: Dict[str, Any]) -> None:
    if result["success"]:
        print(f"ok  tx {result['tx_hash'][:16]}...  balance {result['new_balance']}")
    else:
        _fail(result["error"] or "transaction rejected")


def cmd_transfer(args: argparse.Namespace) -> None:
    client = _client(args)
    _report(client.transfer(_sender(args, client), args.to, args.amount))


def cmd_mint(args: argparse.Namespace) -> None:
    client = _client(args)
    _report(client.mint(_sender(args, client), args.amount))


def cmd_burn(args: argparse.Namespace) -> None:
    client = _client(args)
    _report(client.burn(_sender(args, client), args.amount))


def cmd_stake(args: argparse.Namespace) -> None:
    client = _client(args)
    _report(client.stake(_sender(args, client), args.amount, args.validator))


def cmd_unstake(args: argparse.Namespace) -> None:
    client = _client(args)
    _report(client.unstake(_sender(args, client), args.amount, args.validator))


# ---- Simulation -------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> None:
    client = _client(args)
    node = client.node

    print(
        f"Simulating {args.blocks} blocks x {args.txs_per_block} transfers "
        f"on {len(client.validator_addresses())} validators"
    )
    started = time.perf_counter()
    blocks = client.produce_blocks(args.blocks, args.txs_per_block)
    elapsed = time.perf_counter() - started

    status = node.status()
    submitted = args.blocks * args.txs_per_block
    print(f"\nFinished {len(blocks)} blocks in {elapsed:.3f}s")
    print(f"  final slot        : {status['current_slot']}")
    print(f"  finalized slot    : {status['finalized_slot']}")
    print(f"  total blocks      : {status['total_blocks']}")
    print(f"  total supply      : {status['total_supply']}")
    print(f"  circulating       : {status['circulating_supply']}")
    print(f"  uncirculated      : {status['uncirculated_supply']}")
    print(f"  burned            : {status['burned_supply']}")
    print(f"  supply invariant  : {status['supply_invariant_ok']}")
    print(f"  balance invariant : {node.check_balance_invariant()}")
    print(
        f"  throughput        : {len(blocks) / elapsed:.1f} blocks/s, "
        f"{submitted / elapsed:.1f} transfers/s"
    )
    print(f"  latest block      : {status['latest_block_hash'][:16]}...")


def cmd_invariants(args: argparse.Namespace) -> None:
    client = _client(args)
    node = client.node
    _print_json(
        {
            "supply_invariant_ok": node.check_supply_invariant(),
            "balance_invariant_ok": node.check_balance_invariant(),
            "balances": node.balances_sum(),
            "stakes": node.stakes_sum(),
            "circulating": node.get_circulating_supply(),
            "total": node.get_total_supply(),
        }
    )


# ---- Parser -----------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tachoin",
        description=f"Tachoin ({TOKEN_SYMBOL}) on the Tachyon blockchain",
    )
    parser.add_argument("--version", action="version", version=f"tachoin {__version__}")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--validators", type=int, default=4, help="number of simulated validators"
    )
    common.add_argument(
        "--seeds", nargs="+", default=None, help="hex validator seeds (reproducible)"
    )

    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("create-wallet", help="generate a wallet")
    p.add_argument("--save", default=None, metavar="PATH", help="write the wallet here")
    p.add_argument("--passphrase", default=None, help="encrypt the saved seed")
    p.set_defaults(func=cmd_create_wallet)

    p = sub.add_parser("show-wallet", help="print a wallet file's public data")
    p.add_argument("path")
    p.add_argument("--passphrase", default=None)
    p.set_defaults(func=cmd_show_wallet)

    p = sub.add_parser("status", parents=[common], help="node status")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("supply", parents=[common], help="supply breakdown")
    p.set_defaults(func=cmd_supply)

    p = sub.add_parser("invariants", parents=[common], help="supply and balance invariants")
    p.set_defaults(func=cmd_invariants)

    p = sub.add_parser("validators", parents=[common], help="validator addresses")
    p.set_defaults(func=cmd_validators)

    p = sub.add_parser("balance", parents=[common], help="balance of an address")
    p.add_argument("address")
    p.set_defaults(func=cmd_balance)

    fee = argparse.ArgumentParser(add_help=False)
    fee.add_argument("--from", dest="sender", default=None, help="sender address")
    fee.add_argument("--sender-index", type=int, default=0, help="validator index to send from")

    p = sub.add_parser("transfer", parents=[common, fee], help="transfer TACH")
    p.add_argument("to")
    p.add_argument("amount", help="amount such as 12.5")
    p.set_defaults(func=cmd_transfer)

    p = sub.add_parser("mint", parents=[common, fee], help="mint TACH (validators only)")
    p.add_argument("amount")
    p.set_defaults(func=cmd_mint)

    p = sub.add_parser("burn", parents=[common, fee], help="burn TACH")
    p.add_argument("amount")
    p.set_defaults(func=cmd_burn)

    p = sub.add_parser("stake", parents=[common, fee], help="stake TACH")
    p.add_argument("amount")
    p.add_argument("validator", nargs="?", default=None)
    p.set_defaults(func=cmd_stake)

    p = sub.add_parser("unstake", parents=[common, fee], help="unstake TACH")
    p.add_argument("amount")
    p.add_argument("validator", nargs="?", default=None)
    p.set_defaults(func=cmd_unstake)

    p = sub.add_parser("run", parents=[common], help="block production simulation")
    p.add_argument("--blocks", type=int, default=10)
    p.add_argument("--txs-per-block", type=int, default=3)
    p.set_defaults(func=cmd_run)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
