"""
Dependency injection dung chung: get_current_user, get_trip_or_404...
Tach rieng khoi security.py de tranh circular import (deps can DB session).
"""
from __future__ import annotations

import uuid

from fastapi import Depends, Header
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.trip import Trip
from app.models.user import User


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Doc header Authorization: Bearer <token>, decode JWT, tra ve User tu DB.
    Raise UnauthorizedError (401) neu thieu token, token sai, het han, hoac user khong ton tai.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Thieu token xac thuc")

    token = authorization.removeprefix("Bearer ").strip()

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
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()

    if trip is None:
        raise NotFoundError("Khong tim thay chuyen di")

    if trip.user_id != current_user.id:
        raise ForbiddenError("Ban khong co quyen truy cap chuyen di nay")

    return trip
