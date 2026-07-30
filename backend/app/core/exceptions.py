"""Custom exceptions and global exception handlers."""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import envelope


class AppError(Exception):
    """Base business exception used by services and routers."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Khong tim thay du lieu"):
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Ban khong co quyen truy cap tai nguyen nay"):
        super().__init__(message, status.HTTP_403_FORBIDDEN)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Token khong hop le hoac da het han"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class ConflictError(AppError):
    def __init__(self, message: str = "Du lieu da ton tai"):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


def register_exception_handlers(app: FastAPI) -> None:
    """Register consistent envelope-shaped exception handlers."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return envelope(data=None, message=exc.message, status_code=exc.status_code)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        return envelope(data=None, message=str(exc.detail), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        fields = {str(error.get("loc", [""])[-1]) for error in exc.errors()}
        message = "Validation error"
        if "username" in fields:
            message = "Ten dang nhap khong hop le"
        elif "email" in fields:
            message = "Email khong hop le"
        elif "password" in fields:
            message = "Mat khau khong hop le"
        elif "full_name" in fields:
            message = "Ho va ten khong hop le"

        return envelope(
            data={"detail": exc.errors()},
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        return envelope(
            data=None,
            message="Loi he thong, vui long thu lai sau",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
