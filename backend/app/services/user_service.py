"""Business logic - Module 2: Users."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UpdateProfileRequest


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
