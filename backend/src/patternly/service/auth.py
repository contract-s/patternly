"""Password hashing (scrypt from the standard library) and JWT access tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta

import jwt

ALGORITHM = "HS256"
TOKEN_TTL = timedelta(days=7)
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_b64, digest_b64 = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), **_SCRYPT)
    return hmac.compare_digest(digest, base64.b64decode(digest_b64))


def jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret or len(secret) < 32:
        raise RuntimeError("Set JWT_SECRET to a random string of at least 32 characters before starting the service.")
    return secret


def make_token(learner_id: int, secret: str, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return jwt.encode({"sub": str(learner_id), "iat": now, "exp": now + TOKEN_TTL}, secret, algorithm=ALGORITHM)


def read_token(token: str, secret: str) -> int | None:
    """The learner id in a valid, unexpired token, else None."""
    try:
        return int(jwt.decode(token, secret, algorithms=[ALGORITHM])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
