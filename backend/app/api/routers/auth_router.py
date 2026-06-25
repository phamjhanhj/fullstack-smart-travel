"""Router - Module 1: Auth (4 endpoints)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import envelope, envelope_created
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LoginUserInfo,
    MeResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.services import auth_service
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.register_user(db, payload)
    return envelope_created(
        data=RegisterResponse.model_validate(user),
        message="Dang ky thanh cong",
    )


@router.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.authenticate_user(db, payload.email, payload.password)
    access_token, refresh_token = auth_service.issue_tokens(user.id)

    data = LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
        user=LoginUserInfo.model_validate(user),
    )
    return envelope(data=data, message="Dang nhap thanh cong")


@router.post("/refresh")
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    new_access_token = await auth_service.refresh_access_token(db, payload.refresh_token)
    data = RefreshResponse(access_token=new_access_token, expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    return envelope(data=data, message="Token da duoc lam moi")


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return envelope(data=MeResponse.model_validate(current_user))
