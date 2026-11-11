"""Password hashing and JWT tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from patternly.service.auth import TOKEN_TTL, hash_password, make_token, read_token, verify_password

A, B = "a" * 32, "b" * 32


def test_password_round_trip():
    stored = hash_password("correct horse")
    assert stored.startswith("scrypt$") and "correct horse" not in stored
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong horse", stored)
    assert hash_password("correct horse") != stored  # salted
    assert not verify_password("x", "garbage")


def test_token_round_trip_and_rejections():
    token = make_token(42, A)
    assert read_token(token, A) == 42
    assert read_token(token, B) is None
    assert read_token("not-a-token", A) is None
    old = make_token(42, A, now=datetime.now(UTC) - TOKEN_TTL - timedelta(minutes=1))
    assert read_token(old, A) is None
