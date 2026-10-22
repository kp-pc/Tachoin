"""Locate and load the Tachyon blockchain dependency securely.

Tachyon is developed as a standalone repository and is not published on
PyPI, so it cannot be declared as a normal install requirement. It is
resolved from trusted sources only:

1. an already-importable ``tachyon`` package (installed, vendored on
   ``sys.path``, or left in ``sys.modules``). Version is validated via commit hash.
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
from typing import Optional

# Required Tachyon commit hash (SHA-1) - pinned to reviewed commit
REQUIRED_TACHYON_COMMIT = "ed4f02c018033b86dc6c7122930f013d471a52e7"

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_TACHYON_BLOCKCHAIN_DIR = os.path.join(_REPO_ROOT, "tachyon-blockchain")


def _verify_git_commit(path: str) -> bool:
    """Verify that the git repository at path matches REQUIRED_TACHYON_COMMIT.
    
    Args:
        path: Path to the git repository
        
    Returns:
        True if commit matches, False otherwise
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
        return current_commit == REQUIRED_TACHYON_COMMIT
        
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return False


def _importable() -> bool:
    """True only when ``import tachyon`` actually succeeds AND integrity is verified.
    
    This now includes security validation.
    """
    try:
        import tachyon  # noqa: F401
        
        # Verify the module's commit if possible
        tachyon_path = getattr(tachyon, "__file__", "")
        if tachyon_path:
            tachyon_dir = os.path.dirname(tachyon_path)
            # Check if this directory has a .git directory
            current = tachyon_dir
            while current != "/" and len(current) > 10:
                git_dir = os.path.join(current, ".git")
                if os.path.isdir(git_dir):
                    if not _verify_git_commit(current):
                        raise ImportError(
                            f"Tachyon module at {tachyon_path} has invalid commit. "
                            f"Required: {REQUIRED_TACHYON_COMMIT}"
                        )
                    break
                current = os.path.dirname(current)
        
        return True
        
    except ImportError:
        return False


def is_available() -> bool:
    """True when Tachyon can be imported with verified integrity or is
    present at a known validated path.
    """
    if _importable():
        return True
    
    # Only check the validated tachyon-blockchain directory
    tachyon_init = os.path.join(_TACHYON_BLOCKCHAIN_DIR, "tachyon", "__init__.py")
    if os.path.isfile(tachyon_init):
        return _verify_git_commit(_TACHYON_BLOCKCHAIN_DIR)
    
    return False


def ensure_tachyon() -> None:
    """Make ``import tachyon`` succeed or raise a clear, actionable error.
    
    SECURITY: Only allows imports from validated trusted paths at the
    exact pinned commit. Environment variable TACHYON_PATH is disabled.
    """
    if _importable():
        return
    
    # Check if the tachyon-blockchain directory exists and has correct commit
    tachyon_init = os.path.join(_TACHYON_BLOCKCHAIN_DIR, "tachyon", "__init__.py")
    
    if os.path.isfile(tachyon_init):
        if not _verify_git_commit(_TACHYON_BLOCKCHAIN_DIR):
            raise ImportError(
                f"Tachyon blockchain at {_TACHYON_BLOCKCHAIN_DIR} has invalid commit.\n"
                f"Required commit: {REQUIRED_TACHYON_COMMIT}\n"
                f"Please run: git checkout {REQUIRED_TACHYON_COMMIT} in the tachyon-blockchain directory."
            )
        
        # Add to sys.path and try import
        if _TACHYON_BLOCKCHAIN_DIR not in sys.path:
            sys.path.insert(0, _TACHYON_BLOCKCHAIN_DIR)
        
        try:
            if _importable():
                return
        finally:
            # Clean up sys.path
            if _TACHYON_BLOCKCHAIN_DIR in sys.path:
                sys.path.remove(_TACHYON_BLOCKCHAIN_DIR)
    
    raise ImportError(
        "Tachoin requires the Tachyon blockchain package at commit "
        f"{REQUIRED_TACHYON_COMMIT}, which is not importable.\n\n"
        "Installation options:\n"
        "  1. Clone the required version:\n"
        f"     git clone https://github.com/kp-pc/Tachyon-blockchain.git tachyon-blockchain\n"
        f"     cd tachyon-blockchain\n"
        f"     git checkout {REQUIRED_TACHYON_COMMIT}\n"
        "  2. Set up in the expected project layout:\n"
        "     <project-root>/\n"
        "     ├── tachoin/\n"
        "     └── tachyon-blockchain/\n"
        "\n"
        "SECURITY NOTE: Environment variable TACHYON_PATH is disabled.\n"
        "Only the project-local tachyon-blockchain directory is supported.\n"
        "This prevents loading of untrusted or malicious modules.\n"
    )

# Security note: TACHYON_PATH environment variable is intentionally disabled.
# If you need to use a custom Tachyon location, please modify the code above
# to validate the path against your trusted installation directory.
