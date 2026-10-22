"""Token state: values plus a Merkle commitment.

Tachyon's :class:`~tachyon.smt.SparseMerkleTree` commits to state but does not
read it back, and it is an external, unreleased dependency we must not modify.
:class:`TokenState` therefore owns the authoritative key/value map and mirrors
every write into a Tachyon SMT so block headers can commit to it.

Consequence, by design: :meth:`TokenState.root` is the commitment written into
block headers, and :meth:`TokenState.snapshot` is a copy-on-write view used to
reject a block's state transition without corrupting the parent state.
"""

from __future__ import annotations

from typing import Dict, Iterator, Optional

from ._tachyon import ensure_tachyon

ensure_tachyon()

from tachyon.smt import SparseMerkleTree


class TokenState:
    """Authoritative TACH state with a Merkle root for headers."""

    __slots__ = ("_values", "_tree")

    def __init__(self, values: Optional[Dict[bytes, bytes]] = None):
        self._values: Dict[bytes, bytes] = {}
        self._tree = SparseMerkleTree()
        for key, value in (values or {}).items():
            self.set(key, value)

    # ---- Reads --------------------------------------------------------

    def get(self, key: bytes, default: Optional[bytes] = None) -> Optional[bytes]:
        return self._values.get(key, default)

    def __contains__(self, key: bytes) -> bool:
        return key in self._values

    def __len__(self) -> int:
        return len(self._values)

    def items(self) -> Iterator[tuple[bytes, bytes]]:
        """Iterate ``(key, value)`` pairs in an unspecified order."""
        return iter(self._values.items())

    def keys(self) -> Iterator[bytes]:
        return iter(self._values.keys())

    def root(self) -> bytes:
        """Merkle commitment over the current state."""
        return self._tree.root()

    # ---- Writes -------------------------------------------------------

    def set(self, key: bytes, value: bytes) -> None:
        """Write ``key`` and update the Merkle commitment.

        Deleting (``value`` empty) removes the key so ``root`` reflects the
        absence rather than committing to an empty leaf.
        """
        if not isinstance(key, bytes):
            raise TypeError("state keys must be bytes")
        if not isinstance(value, bytes):
            raise TypeError("state values must be bytes")
        if value:
            self._values[key] = value
        else:
            self._values.pop(key, None)
        self._tree.set(key, value)

    def update(self, pairs: Dict[bytes, bytes]) -> None:
        for key, value in pairs.items():
            self.set(key, value)

    # ---- Snapshots ----------------------------------------------------

    def snapshot(self) -> "TokenState":
        """Return an independent copy sharing no mutable state."""
        clone = TokenState()
        clone._values = dict(self._values)
        # Rebuild the commitment from the copied values; keys are few.
        for key, value in clone._values.items():
            clone._tree.set(key, value)
        return clone

    def restore(self, snapshot: "TokenState") -> None:
        """Replace this state's contents with ``snapshot``."""
        self._values = dict(snapshot._values)
        self._tree = SparseMerkleTree()
        for key, value in self._values.items():
            self._tree.set(key, value)

    def __repr__(self) -> str:
        return f"TokenState(keys={len(self._values)}, root={self.root().hex()[:16]})"
