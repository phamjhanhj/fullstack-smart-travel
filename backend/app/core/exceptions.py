"""Custom exceptions and global exception handlers."""
from __future__ import annotations

import logging
from typing import Any, Final

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import envelope

logger = logging.getLogger("app.error")
FIELD_LABELS: Final = {
    "actual_cost": "Chi phí thực tế",
    "actual_amount": "Số tiền thực chi",
    "actual_total_cost": "Tổng chi phí thực tế",
    "avatar_url": "Ảnh đại diện",
    "booking_url": "Liên kết đặt chỗ",
    "budget": "Ngân sách",
    "budget_mode": "Chế độ ngân sách",
    "bio": "Tiểu sử",
    "category": "Hạng mục",
    "contact_name": "Tên người liên hệ",
    "contact_phone": "Số điện thoại liên hệ",
    "content": "Nội dung",
    "current_password": "Mật khẩu hiện tại",
    "daily_end_time": "Giờ kết thúc mỗi ngày",
    "daily_start_time": "Giờ bắt đầu mỗi ngày",
    "departure_location": "Điểm khởi hành",
    "departure_time": "Giờ khởi hành",
    "description": "Mô tả",
    "destination": "Điểm đến",
    "details": "Nội dung báo cáo",
    "email": "Email",
    "end_date": "Ngày kết thúc",
    "end_time": "Giờ kết thúc",
    "expires_in_days": "Thời hạn lời mời",
    "full_name": "Họ và tên",
    "general_tips": "Lời khuyên chung",
    "label": "Nội dung chi tiêu",
    "login": "Tên đăng nhập hoặc email",
    "message": "Tin nhắn",
    "mobility_notes": "Lưu ý di chuyển",
    "name": "Tên",
    "new_password": "Mật khẩu mới",
    "next_traveler_note": "Ghi chú cho người đi sau",
    "num_travelers": "Số người tham gia",
    "password": "Mật khẩu",
    "phone": "Số điện thoại",
    "planned_amount": "Số tiền dự kiến",
    "preferences": "Sở thích và ghi chú",
    "preferences_json": "Tùy chọn cá nhân",
    "public_bio": "Giới thiệu công khai",
    "public_phone": "Số điện thoại công khai",
    "public_zalo_url": "Liên kết Zalo",
    "rating": "Đánh giá",
    "reason": "Lý do báo cáo",
    "recipient": "Email hoặc tên đăng nhập người nhận",
    "role": "Quyền chia sẻ",
    "source_activity_ids": "Hoạt động nguồn",
    "source_day_number": "Ngày nguồn",
    "start_date": "Ngày bắt đầu",
    "start_time": "Giờ bắt đầu",
    "summary": "Tóm tắt trải nghiệm",
    "target_day_plan_id": "Ngày đích",
    "target_trip_id": "Chuyến đi đích",
    "title": "Tiêu đề",
    "token": "Mã xác minh",
    "travelers": "Số người tham gia",
    "visibility": "Phạm vi hiển thị",
    "username": "Tên đăng nhập",
}


CUSTOM_VALIDATION_MESSAGES: Final[dict[str, tuple[str | None, str]]] = {
    "TRIP_DURATION_TOO_LONG": (
        "end_date",
        "Chuyến đi tối đa 90 ngày. Hãy rút ngắn thời gian hoặc chia thành nhiều chuyến.",
    ),
    "end_time must be later than start_time": ("end_time", "Giờ kết thúc phải sau giờ bắt đầu."),
    "end_date phai lon hon hoac bang start_date": (
        "end_date",
        "Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu.",
    ),
    "start_date is required for full_trip": (
        "start_date",
        "Ngày bắt đầu là bắt buộc khi tạo chuyến đi mới.",
    ),
    "target_day_plan_id is required": ("target_day_plan_id", "Vui lòng chọn ngày đích."),
    "source_day_number is required": ("source_day_number", "Không xác định được ngày nguồn."),
    "source_activity_ids is required": ("source_activity_ids", "Vui lòng chọn ít nhất một hoạt động."),
    "booking_url must be an http or https URL": (
        "booking_url",
        "Liên kết đặt chỗ phải bắt đầu bằng http:// hoặc https://.",
    ),
    "cover_image_url must be an http or https URL": (
        "cover_image_url",
        "Ảnh bìa phải là liên kết http:// hoặc https://.",
    ),
    "avatar_url must be an http, https, or default avatar URL": (
        "avatar_url",
        "Ảnh đại diện không đúng định dạng liên kết được hỗ trợ.",
    ),
    "So dien thoai cong khai khong hop le": ("public_phone", "Số điện thoại công khai không hợp lệ."),
    "So dien thoai ca nhan khong hop le": ("phone", "Số điện thoại không hợp lệ."),
    "Lien ket Zalo phai dung HTTPS va thuoc zalo.me": (
        "public_zalo_url",
        "Liên kết Zalo phải dùng HTTPS và thuộc tên miền zalo.me.",
    ),
    "So dien thoai khong hop le": ("contact_phone", "Số điện thoại liên hệ không hợp lệ."),
    "full_name must contain at least 2 characters": ("full_name", "Họ và tên phải có ít nhất 2 ký tự."),
    "preferences_json must be valid JSON": (
        "preferences_json",
        "Tùy chọn cá nhân không đúng định dạng JSON.",
    ),
}


def _error_field(error: dict[str, Any]) -> str | None:
    location = [str(part) for part in error.get("loc", ()) if str(part) not in {"body", "query", "path"}]
    if location:
        candidate = location[-1]
        if not candidate.isdigit():
            return candidate
    message = str(error.get("msg", ""))
    for marker, (field, _) in CUSTOM_VALIDATION_MESSAGES.items():
        if marker in message:
            return field
    return None


def _validation_message(error: dict[str, Any], field: str | None) -> str:
    error_type = str(error.get("type", ""))
    context = error.get("ctx") or {}
    raw_message = str(error.get("msg", ""))
    label = FIELD_LABELS.get(field or "", (field or "Dữ liệu").replace("_", " ").capitalize())

    for marker, (_, message) in CUSTOM_VALIDATION_MESSAGES.items():
        if marker in raw_message:
            return message
    if error_type == "missing":
        return f"{label} là bắt buộc."
    if error_type in {"string_too_short", "too_short"}:
        minimum = context.get("min_length")
        return f"{label} phải có ít nhất {minimum} ký tự." if minimum is not None else f"{label} quá ngắn."
    if error_type in {"string_too_long", "too_long"}:
        maximum = context.get("max_length")
        return f"{label} không được vượt quá {maximum} ký tự." if maximum is not None else f"{label} quá dài."
    if error_type in {"greater_than_equal", "greater_than"}:
        minimum = context.get("ge", context.get("gt"))
        return f"{label} phải từ {minimum} trở lên."
    if error_type in {"less_than_equal", "less_than"}:
        maximum = context.get("le", context.get("lt"))
        return f"{label} không được lớn hơn {maximum}."
    if error_type == "string_pattern_mismatch":
        return f"{label} không đúng định dạng."
    if error_type in {"date_from_datetime_parsing", "date_parsing"}:
        return f"{label} không phải ngày hợp lệ."
    if error_type in {"int_parsing", "int_type", "float_parsing", "float_type"}:
        return f"{label} phải là một số hợp lệ."
    if error_type in {"literal_error", "enum"}:
        return f"{label} không thuộc lựa chọn được hỗ trợ."
    if error_type == "uuid_parsing":
        return f"{label} không hợp lệ."
    if error_type == "value_error" and raw_message:
        if field == "email":
            return "Email không đúng định dạng."
        cleaned = raw_message.removeprefix("Value error, ").strip()
        return cleaned if cleaned else f"{label} không hợp lệ."
    return f"{label} không hợp lệ."


def validation_error_data(errors: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    normalized_errors: list[dict[str, Any]] = []
    for error in errors:
        field = _error_field(error)
        normalized_errors.append(
            {
                "field": field,
                "code": str(error.get("type", "validation_error")),
                "message": _validation_message(error, field),
            }
        )
    if not normalized_errors:
        normalized_errors.append(
            {"field": None, "code": "validation_error", "message": "Dữ liệu gửi lên không hợp lệ."}
        )
    first = normalized_errors[0]
    return first["message"], {
        "code": "VALIDATION_ERROR",
        "field": first["field"],
        "errors": normalized_errors,
    }


class AppError(Exception):
    """Base business exception used by services and routers."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, data: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.data = data
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
        return envelope(data=exc.data, message=exc.message, status_code=exc.status_code)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        return envelope(data=None, message=str(exc.detail), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        message, data = validation_error_data(exc.errors())

        return envelope(
            data=data,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "Unhandled application exception request_id=%s method=%s path=%s",
            request_id, request.method, request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return envelope(
            data=None,
            message=f"Loi he thong, vui long thu lai sau (ma loi: {request_id})",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
