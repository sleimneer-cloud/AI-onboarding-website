from __future__ import annotations

from functools import lru_cache

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class PasswordManager:
    """Own Argon2id hashing and one reusable dummy verification hash."""

    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        self._hasher = hasher or PasswordHasher(type=Type.ID)
        self._dummy_hash = self._hasher.hash("ix-value-loop-dummy-password")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    def verify_or_dummy(self, password: str, password_hash: str | None) -> bool:
        return self.verify(password_hash or self._dummy_hash, password)


@lru_cache
def get_password_manager() -> PasswordManager:
    return PasswordManager()
