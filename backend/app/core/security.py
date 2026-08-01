"""Password hashing and signed access/refresh tokens."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal
import uuid

import jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")
JWTError = jwt.InvalidTokenError


# ─── Password hashing ─────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def verify_and_update_password(plain_password: str, hashed_password: str) -> tuple[bool, str | None]:
    """Verify a password and return a stronger replacement for legacy hashes."""
    return _pwd_context.verify_and_update(plain_password, hashed_password)


# Performing the same password work for an unknown login reduces account-enumeration timing leaks.
DUMMY_PASSWORD_HASH = hash_password(uuid.uuid4().hex)


# ─── JWT tokens ───────────────────────────────────────────────────────────────

def _create_token(subject: str, expires_in: int, token_type: Literal["access", "refresh"]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "jti": uuid.uuid4().hex,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str) -> str:
    return _create_token(user_id, settings.ACCESS_TOKEN_EXPIRE_SECONDS, "access")


def create_refresh_token(user_id: str) -> str:
    return _create_token(user_id, settings.REFRESH_TOKEN_EXPIRE_SECONDS, "refresh")


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT. Raises JWTError for invalid or expired tokens.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
        options={"require": ["sub", "type", "jti", "iss", "aud", "iat", "exp"]},
    )


__all__ = [
    "hash_password",
    "verify_password",
    "verify_and_update_password",
    "DUMMY_PASSWORD_HASH",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "JWTError",
]
