"""Router - Module 1: Auth (4 endpoints)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import AppError
from app.core.rate_limit import rate_limit
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
    ResendVerificationRequest,
    VerifyEmailRequest,
)
from app.services import auth_service
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", status_code=201, dependencies=[Depends(rate_limit("auth_register", settings.RATE_LIMIT_AUTH_PER_MINUTE))])
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.register_user(db, payload)
    email_sent = True
    try:
        await auth_service.send_verification_for_user(db, user)
    except AppError:
        email_sent = False
    return envelope_created(
        data=RegisterResponse.model_validate(user),
        message="Dang ky thanh cong, hay kiem tra email" if email_sent else "Dang ky thanh cong nhung chua gui duoc email xac minh",
    )


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.verify_email(db, payload.token)
    return envelope(data=None, message="Xac minh email thanh cong")


@router.post("/resend-verification", dependencies=[Depends(rate_limit("auth_resend_verification", 5))])
async def resend_verification(payload: ResendVerificationRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.resend_verification(db, payload.login)
    return envelope(data=None, message="Neu tai khoan can xac minh, email moi da duoc gui")


@router.post("/login", dependencies=[Depends(rate_limit("auth_login", settings.RATE_LIMIT_AUTH_PER_MINUTE))])
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.authenticate_user(db, payload.login, payload.password)
    access_token, refresh_token = await auth_service.issue_tokens(db, user.id)

    data = LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
        user=LoginUserInfo.model_validate(user),
    )
    return envelope(data=data, message="Dang nhap thanh cong")


@router.post("/refresh")
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    new_access_token, new_refresh_token = await auth_service.refresh_access_token(db, payload.refresh_token)
    data = RefreshResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
    )
    return envelope(data=data, message="Token da duoc lam moi")


@router.post("/logout")
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.revoke_refresh_token(db, payload.refresh_token)
    return envelope(data=None, message="Da dang xuat")


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return envelope(data=MeResponse.model_validate(current_user))
