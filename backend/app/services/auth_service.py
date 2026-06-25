"""Business logic - Module 1: Auth."""
from __future__ import annotations

import uuid

from jose import JWTError
from sqlalchemy import select
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
from app.schemas.auth import RegisterRequest


async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    """Dang ky tai khoan moi - kiem tra email da ton tai chua truoc khi tao."""
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise AppError("Email da duoc su dung", status_code=400)

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    """Xac thuc email/password. Raise 401 neu sai (khong tiet lo email co ton tai hay khong)."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Email hoac mat khau khong dung")

    return user


def issue_tokens(user_id: uuid.UUID) -> tuple[str, str]:
    """Tao cap access_token + refresh_token cho user_id."""
    subject = str(user_id)
    return create_access_token(subject), create_refresh_token(subject)


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> str:
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

    return create_access_token(str(user_id))
