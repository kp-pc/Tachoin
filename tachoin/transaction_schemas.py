"""Transaction schemas for Tachoin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Set

from tachoin.exceptions import TransactionError
from tachoin.config import (
    MAX_TRANSFER_AMOUNT,
    MIN_STAKE,
    MAX_STAKE,
    TRANSFER_FEE,
    MINT_FEE,
    TOKEN_DECIMALS,
)
from tachoin.wallet import is_valid_address

# Program identifiers (must match transaction.py)
PROGRAM_TRANSFER = "transfer"
PROGRAM_MINT = "mint"
PROGRAM_BURN = "burn"
PROGRAM_STAKE = "stake"
PROGRAM_UNSTAKE = "unstake"

PROGRAMS = frozenset(
    {PROGRAM_TRANSFER, PROGRAM_MINT, PROGRAM_BURN, PROGRAM_STAKE, PROGRAM_UNSTAKE}
)

SCHEMA_REGISTRY = {
    PROGRAM_TRANSFER: "TransferSchema",
    PROGRAM_MINT: "MintSchema",
    PROGRAM_BURN: "BurnSchema",
    PROGRAM_STAKE: "StakeSchema",
    PROGRAM_UNSTAKE: "UnstakeSchema",
}
class TransferSchema:
    """Schema for transfer transactions."""

    REQUIRED_FIELDS: Set[str] = {"type", "to", "amount", "fee"}
    ALLOWED_FIELDS: Set[str] = {"type", "to", "amount", "fee"}

    @staticmethod
    def validate(data: Dict[str, Any]) -> None:
        """Validate transfer transaction data."""
        # Check required fields
        for field in TransferSchema.REQUIRED_FIELDS:
            if field not in data:
                raise TransactionError(f"missing required field '{field}'")

        # Check unknown fields
        for field in data.keys():
            if field not in TransferSchema.ALLOWED_FIELDS:
                raise TransactionError(f"unknown field '{field}'")

        # Validate field types and values
        if not isinstance(data["type"], str) or data["type"] != PROGRAM_TRANSFER:
            raise TransactionError(f"'type' must be '{PROGRAM_TRANSFER}'")

        if not isinstance(data["to"], str) or not is_valid_address(data["to"]):
            raise TransactionError("recipient is not a valid tachoin address")

        if not isinstance(data["amount"], int) or isinstance(data["amount"], bool):
            raise TransactionError("'amount' must be an integer")
        if data["amount"] < 0:
            raise TransactionError("'amount' cannot be negative")
        if data["amount"] > MAX_TRANSFER_AMOUNT:
            raise TransactionError(
                f"'amount' {data['amount']} exceeds maximum {MAX_TRANSFER_AMOUNT}"
            )

        if not isinstance(data["fee"], int) or isinstance(data["fee"], bool):
            raise TransactionError("'fee' must be an integer")
        if data["fee"] < 0:
            raise TransactionError("'fee' cannot be negative")
        if data["fee"] < TRANSFER_FEE:
            raise TransactionError(f"'fee' must be at least {TRANSFER_FEE}")
class MintSchema:
    """Schema for mint transactions."""

    REQUIRED_FIELDS: Set[str] = {"type", "amount"}
    ALLOWED_FIELDS: Set[str] = {"type", "amount"}

    @staticmethod
    def validate(data: Dict[str, Any]) -> None:
        """Validate mint transaction data."""
        # Check required fields
        for field in MintSchema.REQUIRED_FIELDS:
            if field not in data:
                raise TransactionError(f"missing required field '{field}'")

        # Check unknown fields
        for field in data.keys():
            if field not in MintSchema.ALLOWED_FIELDS:
                raise TransactionError(f"unknown field '{field}'")

        # Validate field types and values
        if not isinstance(data["type"], str) or data["type"] != PROGRAM_MINT:
            raise TransactionError(f"'type' must be '{PROGRAM_MINT}'")

        if not isinstance(data["amount"], int) or isinstance(data["amount"], bool):
            raise TransactionError("'amount' must be an integer")
        if data["amount"] < 0:
            raise TransactionError("'amount' cannot be negative")
        if data["amount"] > MAX_TRANSFER_AMOUNT:
            raise TransactionError(
                f"'amount' {data['amount']} exceeds maximum {MAX_TRANSFER_AMOUNT}"
            )
class BurnSchema:
    """Schema for burn transactions."""

    REQUIRED_FIELDS: Set[str] = {"type", "amount"}
    ALLOWED_FIELDS: Set[str] = {"type", "amount"}

    @staticmethod
    def validate(data: Dict[str, Any]) -> None:
        """Validate burn transaction data."""
        # Check required fields
        for field in BurnSchema.REQUIRED_FIELDS:
            if field not in data:
                raise TransactionError(f"missing required field '{field}'")

        # Check unknown fields
        for field in data.keys():
            if field not in BurnSchema.ALLOWED_FIELDS:
                raise TransactionError(f"unknown field '{field}'")

        # Validate field types and values
        if not isinstance(data["type"], str) or data["type"] != PROGRAM_BURN:
            raise TransactionError(f"'type' must be '{PROGRAM_BURN}'")

        if not isinstance(data["amount"], int) or isinstance(data["amount"], bool):
            raise TransactionError("'amount' must be an integer")
        if data["amount"] < 0:
            raise TransactionError("'amount' cannot be negative")
        if data["amount"] > MAX_TRANSFER_AMOUNT:
            raise TransactionError(
                f"'amount' {data['amount']} exceeds maximum {MAX_TRANSFER_AMOUNT}"
            )
class StakeSchema:
    """Schema for stake transactions."""

    REQUIRED_FIELDS: Set[str] = {"type", "amount"}
    ALLOWED_FIELDS: Set[str] = {"type", "amount", "validator"}

    @staticmethod
    def validate(data: Dict[str, Any]) -> None:
        """Validate stake transaction data."""
        # Check required fields
        for field in StakeSchema.REQUIRED_FIELDS:
            if field not in data:
                raise TransactionError(f"missing required field '{field}'")

        # Check unknown fields
        for field in data.keys():
            if field not in StakeSchema.ALLOWED_FIELDS:
                raise TransactionError(f"unknown field '{field}'")

        # Validate field types and values
        if not isinstance(data["type"], str) or data["type"] != PROGRAM_STAKE:
            raise TransactionError(f"'type' must be '{PROGRAM_STAKE}'")

        if not isinstance(data["amount"], int) or isinstance(data["amount"], bool):
            raise TransactionError("'amount' must be an integer")
        if data["amount"] < 0:
            raise TransactionError("'amount' cannot be negative")
        if data["amount"] < MIN_STAKE:
            raise TransactionError(f"'amount' must be at least {MIN_STAKE}")
        if data["amount"] > MAX_STAKE:
            raise TransactionError(f"'amount' exceeds maximum {MAX_STAKE}")

        if "validator" in data:
            if not isinstance(data["validator"], str) or not is_valid_address(
                data["validator"]
            ):
                raise TransactionError("validator is not a valid tachoin address")
class UnstakeSchema:
    """Schema for unstake transactions."""

    REQUIRED_FIELDS: Set[str] = {"type", "amount"}
    ALLOWED_FIELDS: Set[str] = {"type", "amount", "validator"}

    @staticmethod
    def validate(data: Dict[str, Any]) -> None:
        """Validate unstake transaction data."""
        # Check required fields
        for field in UnstakeSchema.REQUIRED_FIELDS:
            if field not in data:
                raise TransactionError(f"missing required field '{field}'")

        # Check unknown fields
        for field in data.keys():
            if field not in UnstakeSchema.ALLOWED_FIELDS:
                raise TransactionError(f"unknown field '{field}'")

        # Validate field types and values
        if not isinstance(data["type"], str) or data["type"] != PROGRAM_UNSTAKE:
            raise TransactionError(f"'type' must be '{PROGRAM_UNSTAKE}'")

        if not isinstance(data["amount"], int) or isinstance(data["amount"], bool):
            raise TransactionError("'amount' must be an integer")
        if data["amount"] < 0:
            raise TransactionError("'amount' cannot be negative")
        if data["amount"] < MIN_STAKE:
            raise TransactionError(f"'amount' must be at least {MIN_STAKE}")
        if data["amount"] > MAX_STAKE:
            raise TransactionError(f"'amount' exceeds maximum {MAX_STAKE}")

        if "validator" in data:
            if not isinstance(data["validator"], str) or not is_valid_address(
                data["validator"]
            ):
                raise TransactionError("validator is not a valid tachoin address")
def validate_payload_schema(program: str, data: Dict[str, Any]) -> None:
    """Validate transaction payload using strict schema."""
    if program not in SCHEMA_REGISTRY:
        raise TransactionError(f"unknown program '{program}'")

    schema_class_name = SCHEMA_REGISTRY[program]
    
    # Map schema class names to actual classes
    schema_classes = {
        "TransferSchema": TransferSchema,
        "MintSchema": MintSchema,
        "BurnSchema": BurnSchema,
        "StakeSchema": StakeSchema,
        "UnstakeSchema": UnstakeSchema,
    }
    
    schema_class = schema_classes[schema_class_name]
    schema_class.validate(data)

def validate_transaction(transaction_data):
    """Validate a transaction."""
    program = transaction_data.get("program")
    data = transaction_data.get("data")
    
    if program not in SCHEMA_REGISTRY:
        raise TransactionError(f"unknown program '{program}'")

    schema_class_name = SCHEMA_REGISTRY[program]
    schema_classes = {
        "TransferSchema": TransferSchema,
        "MintSchema": MintSchema,
        "BurnSchema": BurnSchema,
        "StakeSchema": StakeSchema,
        "UnstakeSchema": UnstakeSchema,
    }
    
    schema_class = schema_classes[schema_class_name]
    schema_class.validate(data)

def normalize_error(error: Exception) -> str:
    """Convert various exceptions to normalized error messages.

    Raises TransactionError with normalized message for invalid transactions.
    Preserves programming errors (TypeError, ValueError) only when they're
    part of normal untrusted transaction processing.
    """
    if isinstance(error, TransactionError):
        return str(error)
    elif isinstance(error, (KeyError, TypeError, ValueError)):
        # Convert to TransactionError for consistent error handling
        return f"transaction validation failed: {str(error)}"
    else:
        # Re-raise unexpected programming errors
        raise
