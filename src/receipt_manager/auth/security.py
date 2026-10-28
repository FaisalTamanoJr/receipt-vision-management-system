"""
Password hashing. New hashes use argon2.

Databases seeded before the auth service existed have
"scrypt$<salt hex>$<hash hex>" hashes, those still verify and
needs_rehash() tells the auth service to replace them on the next login.

Helpful reference:
https://argon2-cffi.readthedocs.io/en/stable/api.html
"""

import hashlib
import hmac

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _check_scrypt(stored_hash: str, password: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored_hash.split("$")
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
    except ValueError:
        return False
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(digest, expected)


def check_password(stored_hash: str, password: str) -> bool:
    if stored_hash.startswith("scrypt$"):
        return _check_scrypt(stored_hash, password)
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return stored_hash.startswith("scrypt$") or _hasher.check_needs_rehash(stored_hash)
