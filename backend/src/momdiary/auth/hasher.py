"""Argon2id password hashing — feature 006 (research §R1).

Defaults follow OWASP minimums (time_cost=3, memory_cost=64 MiB, parallelism=4).
We rely on the `argon2-cffi` `PasswordHasher` for both hashing and the
``check_needs_rehash`` path so parameters can be raised later without a
schema migration: stored hashes are PHC strings that fully self-describe.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerifyMismatchError,
)


class PasswordHasherService:
    """Thin façade around argon2.PasswordHasher with strict types."""

    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        # PasswordHasher() defaults: time_cost=3, memory_cost=65536 (KiB),
        # parallelism=4, hash_len=32, salt_len=16 — OWASP-aligned.
        self._ph = hasher or PasswordHasher()

    def hash(self, password: str) -> str:
        """Return a PHC-encoded Argon2id hash string."""
        return self._ph.hash(password)

    def verify(self, hash_str: str, password: str) -> bool:
        """True iff the password matches the hash. Never raises on mismatch."""
        try:
            self._ph.verify(hash_str, password)
        except (VerifyMismatchError, InvalidHashError):
            return False
        return True

    def needs_rehash(self, hash_str: str) -> bool:
        """True when the stored hash uses weaker-than-current parameters."""
        return self._ph.check_needs_rehash(hash_str)

    def dummy_verify(self) -> None:
        """Constant-time dummy verify (mitigates user-enumeration on login)."""
        try:
            self._ph.verify(
                "$argon2id$v=19$m=65536,t=3,p=4$"
                "c29tZXNhbHQ$"
                "/yEKZS9k0bGc9wL9pZ6yjlSyB3eqJrCRgPCAm9wMrnE",
                "x",
            )
        except (VerifyMismatchError, InvalidHashError):
            pass


_default: PasswordHasherService | None = None


def get_password_hasher() -> PasswordHasherService:
    """Process-singleton (PasswordHasher is thread-safe and stateless)."""
    global _default
    if _default is None:
        _default = PasswordHasherService()
    return _default
