"""Transaction schemas for Tachoin."""

SCHEMA_REGISTRY = {}

# Constants from transaction_schemas.py
PROGRAM_TRANSFER = "transfer"
PROGRAM_MINT = "mint"
PROGRAM_UNSTAKE = "unstake"

# Module-level definitions
from tachoin.transaction import TransactionError

def validate_transaction(transaction_data):
    """Validate a transaction."""
    program = transaction_data.get("program")
    data = transaction_data.get("data")
    
    if program not in SCHEMA_REGISTRY:
        raise TransactionError(f"unknown program '{program}'")

    schema_class = SCHEMA_REGISTRY[program]
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
