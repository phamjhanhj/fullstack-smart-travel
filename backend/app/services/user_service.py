"""Business logic - Module 2: Users."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.user import ChangePasswordRequest, UpdateProfileRequest


async def update_profile(db: AsyncSession, user: User, payload: UpdateProfileRequest) -> User:
    """Cap nhat tung field duoc gui len (PATCH semantics) - bo qua field None."""
    update_data = payload.model_dump(exclude_unset=True, exclude_none=False)

    for field, value in update_data.items():
        if field == "preferences_json" and value is not None:
            # value la UserPreferences object hoac dict tu model_dump -> luu dang dict (JSON column)
            value = value if isinstance(value, dict) else value.model_dump()
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


async def change_password(db: AsyncSession, user: User, payload: ChangePasswordRequest) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise AppError("Mat khau hien tai khong dung")
    if verify_password(payload.new_password, user.password_hash):
        raise AppError("Mat khau moi phai khac mat khau hien tai")

    user.password_hash = hash_password(payload.new_password)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()
