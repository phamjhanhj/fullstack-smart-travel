"""Router - Module 1: Auth (4 endpoints)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import AppError, UnauthorizedError
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
REFRESH_COOKIE_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_SECONDS,
        path=REFRESH_COOKIE_PATH,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )


def _refresh_token(request: Request, payload: RefreshRequest | None) -> str | None:
    if payload and payload.refresh_token:
        return payload.refresh_token
    return request.cookies.get(settings.REFRESH_COOKIE_NAME)


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


@router.post("/verify-email", dependencies=[Depends(rate_limit("auth_verify_email", settings.RATE_LIMIT_AUTH_PER_MINUTE))])
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
        expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
        user=LoginUserInfo.model_validate(user),
    )
    response = envelope(data=data, message="Dang nhap thanh cong")
    _set_refresh_cookie(response, refresh_token)
    return response


@router.post("/refresh", dependencies=[Depends(rate_limit("auth_refresh", 20))])
async def refresh(
    request: Request,
    payload: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    token = _refresh_token(request, payload)
    if not token:
        raise UnauthorizedError("Phien dang nhap khong hop le hoac da het han")
    new_access_token, new_refresh_token = await auth_service.refresh_access_token(db, token)
    data = RefreshResponse(
        access_token=new_access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
    )
    response = envelope(data=data, message="Token da duoc lam moi")
    _set_refresh_cookie(response, new_refresh_token)
    return response


@router.post("/logout", dependencies=[Depends(rate_limit("auth_logout", 30))])
async def logout(
    request: Request,
    payload: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    token = _refresh_token(request, payload)
    if token:
        await auth_service.revoke_refresh_token(db, token)
    response = envelope(data=None, message="Da dang xuat")
    _clear_refresh_cookie(response)
    return response


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return envelope(data=MeResponse.model_validate(current_user))
