"""
Custom exceptions + global exception handlers.
Đảm bảo MỌI lỗi trả về (400/401/403/404/422/500) đều theo đúng envelope
{ status_code, message, data } như API spec yêu cầu — bao gồm cả lỗi
validation tự động của FastAPI/Pydantic (422).
"""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import envelope


class AppError(Exception):
    """Base exception cho lỗi nghiệp vụ — dùng trong services/routers."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Không tìm thấy dữ liệu"):
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Bạn không có quyền truy cập tài nguyên này"):
        super().__init__(message, status.HTTP_403_FORBIDDEN)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Token không hợp lệ hoặc đã hết hạn"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class ConflictError(AppError):
    def __init__(self, message: str = "Dữ liệu đã tồn tại"):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


def register_exception_handlers(app: FastAPI) -> None:
    """Đăng ký toàn bộ exception handler vào app FastAPI — gọi 1 lần trong main.py."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return envelope(data=None, message=exc.message, status_code=exc.status_code)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        # Bắt các HTTPException mặc định (vd: 404 route không tồn tại)
        return envelope(data=None, message=str(exc.detail), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        # Format lại lỗi Pydantic 422 đúng theo ví dụ trong API spec
        return envelope(
            data={"detail": exc.errors()},
            message="Validation error",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        # Fallback cho mọi lỗi không lường trước — không để leak stack trace ra ngoài
        return envelope(
            data=None,
            message="Lỗi hệ thống, vui lòng thử lại sau",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
