"""Business logic - Module 1: Auth."""
from __future__ import annotations

import uuid
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, UnauthorizedError
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    JWTError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_and_update_password,
)
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.account_token import AccountToken
from app.schemas.auth import RegisterRequest
from app.services import email_service


async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    """Dang ky tai khoan moi voi ten dang nhap duy nhat."""
    normalized_username = payload.username.lower()
    existing = await db.execute(select(User).where(func.lower(User.username) == normalized_username))
    if existing.scalar_one_or_none() is not None:
        raise AppError("Ten dang nhap da duoc su dung", status_code=400)

    normalized_email = str(payload.email).lower()
    existing_email = await db.execute(select(User).where(func.lower(User.email) == normalized_email))
    if existing_email.scalar_one_or_none() is not None:
        raise AppError("Email da duoc su dung", status_code=400)

    user = User(
        username=normalized_username,
        email=normalized_email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError("Ten dang nhap hoac email da duoc su dung", status_code=400)
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, login: str, password: str) -> User:
    """Xac thuc bang username hoac email ma khong tiet lo tai khoan co ton tai hay khong."""
    normalized_login = login.lower()
    result = await db.execute(
        select(User).where(
            (func.lower(User.username) == normalized_login)
            | (func.lower(User.email) == normalized_login)
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        raise UnauthorizedError("Ten dang nhap, email hoac mat khau khong dung")

    password_valid, upgraded_hash = verify_and_update_password(password, user.password_hash)
    if not password_valid:
        raise UnauthorizedError("Ten dang nhap, email hoac mat khau khong dung")

    if user.email and user.email_verified_at is None:
        raise AppError("Email chua duoc xac minh", status_code=403)

    if upgraded_hash:
        user.password_hash = upgraded_hash
        await db.commit()
        await db.refresh(user)

    return user


async def send_verification_for_user(db: AsyncSession, user: User) -> None:
    if not user.email or user.email_verified_at is not None:
        return
    now = datetime.now(timezone.utc)
    await db.execute(
        update(AccountToken)
        .where(
            AccountToken.user_id == user.id,
            AccountToken.token_type == "email_verification",
            AccountToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    token = secrets.token_urlsafe(48)
    db.add(
        AccountToken(
            user_id=user.id,
            token_hash=_hash_token(token),
            token_type="email_verification",
            expires_at=now + timedelta(hours=24),
        )
    )
    await db.commit()
    await email_service.send_verification_email(user.email, user.full_name, token)


async def resend_verification(db: AsyncSession, login: str) -> None:
    result = await db.execute(
        select(User).where(
            (func.lower(User.username) == login.lower())
            | (func.lower(User.email) == login.lower())
        )
    )
    user = result.scalar_one_or_none()
    if user is not None:
        await send_verification_for_user(db, user)


async def verify_email(db: AsyncSession, token: str) -> User:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(AccountToken)
        .where(
            AccountToken.token_hash == _hash_token(token),
            AccountToken.token_type == "email_verification",
            AccountToken.used_at.is_(None),
        )
        .with_for_update()
    )
    stored = result.scalar_one_or_none()
    expires_at = stored.expires_at if stored else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if stored is None or expires_at is None or expires_at < now:
        raise AppError("Lien ket xac minh khong hop le hoac da het han")
    user_result = await db.execute(select(User).where(User.id == stored.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise AppError("Tai khoan khong ton tai")
    user.email_verified_at = now
    stored.used_at = now
    await db.commit()
    await db.refresh(user)
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
        select(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
        .with_for_update()
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
