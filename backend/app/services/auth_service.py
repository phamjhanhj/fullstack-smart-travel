"""Business logic - Module 1: Auth."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from jose import JWTError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas.auth import RegisterRequest


async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    """Dang ky tai khoan moi - kiem tra email da ton tai chua truoc khi tao."""
    normalized_email = payload.email.lower()
    existing = await db.execute(select(User).where(func.lower(User.email) == normalized_email))
    if existing.scalar_one_or_none() is not None:
        raise AppError("Email da duoc su dung", status_code=400)

    user = User(
        email=normalized_email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    """Xac thuc email/password. Raise 401 neu sai (khong tiet lo email co ton tai hay khong)."""
    result = await db.execute(select(User).where(func.lower(User.email) == email.lower()))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Email hoac mat khau khong dung")

    return user


def _hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


async def issue_tokens(db: AsyncSession, user_id: uuid.UUID) -> tuple[str, str]:
    """Tao cap access_token + refresh_token cho user_id va luu hash refresh token."""
    subject = str(user_id)
    access_token = create_access_token(subject)
    refresh_token = create_refresh_token(subject)
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=_hash_token(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.REFRESH_TOKEN_EXPIRE_SECONDS),
        )
    )
    await db.commit()
    return access_token, refresh_token


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    """
    Verify refresh_token con hop le, user van ton tai trong DB,
    roi cap access_token moi. Khong cap refresh_token moi (giu nguyen theo spec).
    """
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise UnauthorizedError("Token khong hop le hoac da het han")

    if payload.get("type") != "refresh":
        raise UnauthorizedError("Token khong hop le hoac da het han")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise UnauthorizedError("Token khong hop le hoac da het han")

    result = await db.execute(select(User).where(User.id == user_id))
    if result.scalar_one_or_none() is None:
        raise UnauthorizedError("Token khong hop le hoac da het han")

    token_hash = _hash_token(refresh_token)
    token_result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    stored_token = token_result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    expires_at = stored_token.expires_at if stored_token is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if stored_token is None or expires_at is None or expires_at < now:
        raise UnauthorizedError("Token khong hop le hoac da het han")

    stored_token.revoked_at = now
    new_access_token = create_access_token(str(user_id))
    new_refresh_token = create_refresh_token(str(user_id))
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=_hash_token(new_refresh_token),
            expires_at=now + timedelta(seconds=settings.REFRESH_TOKEN_EXPIRE_SECONDS),
        )
    )
    await db.commit()
    return new_access_token, new_refresh_token


async def revoke_refresh_token(db: AsyncSession, refresh_token: str) -> None:
    token_hash = _hash_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    stored_token = result.scalar_one_or_none()
    if stored_token is not None:
        stored_token.revoked_at = datetime.now(timezone.utc)
        await db.commit()
