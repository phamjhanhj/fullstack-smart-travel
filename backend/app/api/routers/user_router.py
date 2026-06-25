"""Router - Module 2: Users (2 endpoints)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import envelope
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UpdateProfileRequest, UserProfileResponse
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
async def get_profile(current_user: User = Depends(get_current_user)):
    return envelope(data=UserProfileResponse.model_validate(current_user))


@router.patch("/me")
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated_user = await user_service.update_profile(db, current_user, payload)
    return envelope(
        data=UserProfileResponse.model_validate(updated_user),
        message="Cap nhat thanh cong",
    )
