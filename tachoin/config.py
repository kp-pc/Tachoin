"""Tachoin network constants and configuration."""

# Network identifier
NETWORK_ID = "tachoin-mainnet"
TESTNET_ID = "tachoin-testnet"

# Token metadata
TOKEN_NAME = "Tachoin"
TOKEN_SYMBOL = "TACH"
TOKEN_DECIMALS = 18

# Supply
TOTAL_SUPPLY = 100_000_000 * (10 ** TOKEN_DECIMALS)  # 100 million TACH in least units
GENESIS_REWARD_POOL = 1_000_000 * (10 ** TOKEN_DECIMALS)

# Staking
MIN_STAKE = 100 * (10 ** TOKEN_DECIMALS)
MAX_STAKE = 10_000_000 * (10 ** TOKEN_DECIMALS)
STAKE_REWARD_RATE = 0.05  # 5% APY
UNSTAKE_COOLDOWN_SLOTS = 400  # ~160 s at 400 ms/slot

# Fees
TRANSFER_FEE = 1_000  # in least units (0.000001 TACH)
MINT_FEE = 10_000

# Slot timing (inherited from Tachyon)
SLOT_MS = 400
SLOTS_PER_EPOCH = 400

# Address prefix (matches wallet.py)
ADDR_PREFIX = "tach"

# State keys (domain-separated for Tachyon's SMT)
STATE_KEY_TOTAL_SUPPLY = b"tachoin/total_supply"
STATE_KEY_CIRCULATING_SUPPLY = b"tachoin/circulating_supply"
STATE_KEY_BURNED_SUPPLY = b"tachoin/burned_supply"


def balance_key(address: str) -> bytes:
    """Return the SMT key for a given tachoin address balance."""
    from tachyon.encoding import digest
    return digest("tachoin_balance", address.encode("utf-8"))


def stake_key(address: str) -> bytes:
    """Return the SMT key for a given tachoin address stake amount."""
    from tachyon.encoding import digest
    return digest("tachoin_stake", address.encode("utf-8"))


def nonce_key(address: str) -> bytes:
    """Return the SMT key for a given tachoin address transaction nonce."""
    from tachyon.encoding import digest
    return digest("tachoin_nonce", address.encode("utf-8"))
