"""Locate and load the Tachyon blockchain dependency.

Tachyon is developed as a standalone repository and is not published on
PyPI, so it cannot be declared as a normal install requirement.  It is
resolved from, in order:

1. an already-importable ``tachyon`` package (installed, vendored on
   ``sys.path``, or left in ``sys.modules``),
2. the directory named by the ``TACHYON_PATH`` environment variable,
3. the development sibling checkout ``<repo>/tachyon-blockchain``,
4. ``tachyon-blockchain`` or ``tachyon`` beside the current working directory.

Every Tachoin module calls :func:`ensure_tachyon` before importing any
``tachyon.*`` module, so the resolution logic lives in exactly one place.
"""

from __future__ import annotations

import os
import sys
from typing import Iterator

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)


def _candidate_dirs() -> Iterator[str]:
    """Yield directories that may contain a ``tachyon`` package."""
    env = os.environ.get("TACHYON_PATH")
    if env:
        yield os.path.abspath(os.path.expanduser(env))

    # Development layout: <repo>/tachyon-blockchain/tachyon
    yield os.path.join(_REPO_ROOT, "tachyon-blockchain")

    cwd = os.path.abspath(os.getcwd())
    yield os.path.join(cwd, "tachyon-blockchain")
    yield cwd


def _importable() -> bool:
    """True only when ``import tachyon`` actually succeeds right now."""
    try:
        import tachyon  # noqa: F401
    except ImportError:
        return False
    return True


def is_available() -> bool:
    """True when Tachyon can be imported or is present at a known path."""
    if _importable():
        return True
    return any(
        os.path.isfile(os.path.join(path, "tachyon", "__init__.py"))
        for path in _candidate_dirs()
    )


def ensure_tachyon() -> None:
    """Make ``import tachyon`` succeed or raise a clear, actionable error."""
    if _importable():
        return

    for directory in _candidate_dirs():
        if not os.path.isfile(os.path.join(directory, "tachyon", "__init__.py")):
            continue
        if directory not in sys.path:
            sys.path.insert(0, directory)
        if _importable():
            return

    raise ImportError(
        "Tachoin requires the Tachyon blockchain package, which is not "
        "importable.\n"
        "Clone it next to this project:\n"
        "  git clone https://github.com/kp-pc/Tachyon-blockchain.git "
        "tachyon-blockchain\n"
        "or set TACHYON_PATH to an existing checkout."
    )
