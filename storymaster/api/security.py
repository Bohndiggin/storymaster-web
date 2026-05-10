"""Password hashing primitives.

Argon2id with the library defaults — adequate for a small-team deploy. Wrapped
so the rest of the codebase doesn't import argon2 directly.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password must not be empty")
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    if not stored_hash or not password:
        return False
    try:
        _hasher.verify(stored_hash, password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)
