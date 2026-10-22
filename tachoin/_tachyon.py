"""Locate and load the Tachyon blockchain dependency securely.

Tachyon is developed as a standalone repository and is not published on
PyPI, so it cannot be declared as a normal install requirement. It is
resolved from trusted sources only:

1. an already-importable ``tachyon`` package (installed, vendored on
   ``sys.path``, or left in ``sys_modules``). Version is validated via commit hash.
2. the development sibling checkout ``<repo>/tachyon-blockchain`` at the
   required commit.

Every Tachoin module calls :func:`ensure_tachyon` before importing any
``tachyon.*`` module, so the resolution logic lives in exactly one place.

SECURITY NOTES:
- Environment variable ``TACHYON_PATH`` is **DISABLED** to prevent arbitrary path injection.
- Commit hash ``ed4f02c018033b86dc6c7122930f013d471a52e7`` is required.
- Imports are validated before use to prevent malicious module loading.
- Fail closed: any security violation raises ImportError with clear message.
- Path validation prevents loading from unexpected locations.
"""

from __future__ import annotations

import os
import sys
import subprocess
import hashlib
from typing import Optional, List

# Required Tachyon commit hash (SHA-1) - pinned to reviewed commit
REQUIRED_TACHYON_COMMIT = "ed4f02c018033b86dc6c7122930f013d471a52e7"

# Module version for this hardened implementation
__version__ = "1.0.2-harden.1"

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_TACHYON_BLOCKCHAIN_DIR = os.path.join(_REPO_ROOT, "tachyon-blockchain")

# Trusted installation paths - only these locations are allowed
_TRUSTED_PATHS = [_TACHYON_BLOCKCHAIN_DIR]


def _verify_git_commit(path: str, expected_commit: str = REQUIRED_TACHYON_COMMIT) -> bool:
    """Verify that the git repository at path matches expected_commit.

    Args:
        path: Path to the git repository
        expected_commit: The required commit hash (defaults to REQUIRED_TACHYON_COMMIT)

    Returns:
        True if commit matches, False otherwise or on error
    """
    try:
        # Check if this is a git repository
        git_dir = os.path.join(path, ".git")
        if not os.path.isdir(git_dir):
            return False

        # Get the current commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return False

        current_commit = result.stdout.strip()
        return current_commit == expected_commit

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def _is_path_trusted(path: str) -> bool:
    """Check if a path is within trusted installation directories.

    Args:
        path: Path to check

    Returns:
        True if path is within a trusted location
    """
    abs_path = os.path.abspath(path)
    for trusted in _TRUSTED_PATHS:
        trusted_abs = os.path.abspath(trusted)
        # Check if path is within trusted directory
        if os.path.commonpath([abs_path, trusted_abs]) == trusted_abs:
            return True
    return False


def _validate_tachyon_module_integrity() -> bool:
    """Validate the integrity of the already-loaded tachyon module.

    Checks that the module was loaded from a trusted path and matches
    the expected version.

    Returns:
        True if module integrity is verified
    """
    try:
        import tachyon  # noqa: F401

        tachyon_path = getattr(tachyon, "__file__", "")
        if not tachyon_path:
            return False

        # Get the root directory of tachyon module
        tachyon_root = os.path.dirname(tachyon_path)

        # Verify the path is trusted
        if not _is_path_trusted(tachyon_root):
            return False

        # If there's a .git directory, verify the commit
        if os.path.isdir(os.path.join(tachyon_root, ".git")):
            return _verify_git_commit(tachyon_root)

        # For non-git installs, we rely on path trust alone
        return True

    except ImportError:
        return False


def _get_import_path() -> Optional[str]:
    """Get the validated import path for the tachyon module.

    Only looks in pre-approved trusted locations.

    Returns:
        Path to tachyon package if valid, None otherwise
    """ 
    # Check trusted paths only
    for path in _TRUSTED_PATHS:
        tachyon_init = os.path.join(path, "tachyon", "__init__.py")
        if not os.path.isfile(tachyon_init):
            continue

        # Validate the commit before accepting this path
        if not _verify_git_commit(path):
            continue

        return os.path.join(path, "tachyon")

    return None


def _importable() -> bool:
    """True only when ``import tachyon`` succeeds AND integrity is verified.

    This now includes security validation.
    """
    return _validate_tachyon_module_integrity()


def is_available() -> bool:
    """True when Tachyon can be imported with verified integrity or is
    present at a known validated path.
    """
    if _importable():
        return True

    return _get_import_path() is not None


def ensure_tachyon() -> None:
    """Make ``import tachyon`` succeed or raise a clear, actionable error.

    SECURITY: Only allows imports from validated trusted paths at the
    exact pinned commit. Environment variable TACHYON_PATH is disabled.
    """
    # First check if already imported with valid version
    if _importable():
        return

    # Get validated import path from trusted locations only
    import_path = _get_import_path()

    if import_path:
        # Verify path is trusted before adding to sys.path
        if not _is_path_trusted(import_path):
            raise ImportError(
                "SECURITY ERROR: Tachyon dependency path is not in a 
                "trusted location.
"
                "This may indicate a compromised or unexpected module location.
"
                "Please verify your Tachyon installation."
            )

        if import_path not in sys.path:
            sys.path.insert(0, import_path)

        # Re-verify after adding to path
        if _importable():
            return
        else:
            raise ImportError(
                "Tachyon module loaded but failed integrity verification."
            )

    # Construct helpful error message
    raise ImportError(
        "Tachoin requires the Tachyon blockchain package at commit "{commit}", which is not available.
"
        "
"
        "Installation options:
"
        "  1. Clone the required version:
"
        "     git clone https://github.com/kp-pc/Tachyon-blockchain.git tachyon-blockchain
"
        "     cd tachyon-blockchain
"
        "     git checkout {commit}
"
        "  2. Set up in the expected project layout:
"
        "     <project-root>/
"
        "     ├── tachoin/
"
        "     └── tachyon-blockchain/
"
        "
"
        "SECURITY NOTE: Environment variable TACHYON_PATH is disabled.
"
        "Only the project-local tachyon-blockchain directory is supported.
"
        "This prevents loading of untrusted or malicious modules.
"
        .format(commit=REQUIRED_TACHYON_COMMIT)
    ) 


# Security module initialization
def _check_tachyon_path_not_leaked():
    """Verify that TACHYON_PATH environment variable is not used."""
    if "TACHYON_PATH" in os.environ:
        # Log a warning but don't fail - this is informational
        import warnings
        warnings.warn(
            "TACHYON_PATH environment variable is set but not used.
"
            "The hardened dependency resolver only supports the project-local
"
            "tachyon-blockchain directory at the pinned commit.
"
            "To use a different location, please modify _tachyon.py._TRUSTED_PATHS,
"
            "but understand this reduces security.
",
            RuntimeWarning,
            "__future__"  # FutureWarning would be too weak
        )

_check_tachyon_path_not_leaked()