"""
Dependency injection dung chung: get_current_user, get_trip_or_404...
Tach rieng khoi security.py de tranh circular import (deps can DB session).
"""
from __future__ import annotations

import uuid

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import JWTError, decode_token
from app.db.session import get_db
from app.models.trip import Trip
from app.models.user import User
from app.services import trip_share_service


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, separator, token = authorization.partition(" ")
    token = token.strip()
    if separator != " " or scheme.lower() != "bearer" or not token or len(token) > 4096:
        return None
    return token


async def get_optional_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Return the signed-in user when a valid access token is present, otherwise None."""
    token = _bearer_token(authorization)
    if token is None:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Doc header Authorization: Bearer <token>, decode JWT, tra ve User tu DB.
    Raise UnauthorizedError (401) neu thieu token, token sai, het han, hoac user khong ton tai.
    """
    token = _bearer_token(authorization)
    if token is None:
        raise UnauthorizedError("Thieu token xac thuc")

    try:
        payload = decode_token(token)
    except JWTError:
        raise UnauthorizedError("Token khong hop le hoac da het han")

    if payload.get("type") != "access":
        raise UnauthorizedError("Token khong hop le hoac da het han")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise UnauthorizedError("Token khong hop le hoac da het han")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("Token khong hop le hoac da het han")

    return user


async def get_owned_trip(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Trip:
    """
    Lay Trip theo trip_id, kiem tra thuoc ve current_user.
    Dung lam dependency chung cho moi route co {trip_id} trong path
    -> tranh lap code kiem tra quyen o tung router.
    """
    return await trip_share_service.get_owned_trip_or_404(db, trip_id, current_user.id)


async def get_trip_read_access(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Trip:
    return await trip_share_service.get_accessible_trip_or_404(db, trip_id, current_user.id)


async def get_trip_edit_access(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Trip:
    return await trip_share_service.get_editable_trip_or_404(db, trip_id, current_user.id)


async def get_trip_owner_access(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Trip:
    return await trip_share_service.get_owned_trip_or_404(db, trip_id, current_user.id)


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    admin_emails = settings.admin_email_set
    if not admin_emails or (current_user.email or "").lower() not in admin_emails:
        raise ForbiddenError("Ban khong co quyen truy cap chuc nang quan tri")
    return current_user
