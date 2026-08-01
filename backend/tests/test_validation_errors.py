from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from app.core.exceptions import validation_error_data
from app.schemas.day_plan import CreateActivityRequest
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.p2_features import BookingInquiryCreate
from app.schemas.public_trip import PublicTripImportRequest
from app.schemas.trip import CreateTripRequest
from app.schemas.user import UserPreferences


def _normalized(exc: ValidationError) -> tuple[str, dict]:
    return validation_error_data(exc.errors())


def test_field_validation_error_has_vietnamese_message_and_field() -> None:
    with pytest.raises(ValidationError) as exc_info:
        BookingInquiryCreate(contact_name="A", contact_phone="abc", travelers=101)

    message, data = _normalized(exc_info.value)

    assert message == "Tên người liên hệ phải có ít nhất 2 ký tự."
    assert data["code"] == "VALIDATION_ERROR"
    assert data["field"] == "contact_name"
    assert {item["field"] for item in data["errors"]} == {
        "contact_name",
        "contact_phone",
        "travelers",
    }


def test_model_validation_error_is_mapped_to_end_time() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateActivityRequest(title="Ăn sáng", start_time="09:00", end_time="08:00")

    message, data = _normalized(exc_info.value)

    assert message == "Giờ kết thúc phải sau giờ bắt đầu."
    assert data["field"] == "end_time"


def test_import_model_error_is_mapped_to_required_start_date() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PublicTripImportRequest(import_mode="full_trip")

    message, data = _normalized(exc_info.value)

    assert message == "Ngày bắt đầu là bắt buộc khi tạo chuyến đi mới."
    assert data["field"] == "start_date"


def test_registration_value_errors_do_not_leak_english_messages() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RegisterRequest(username="valid-user", email="not-an-email", password="123456", full_name="A")

    _, data = _normalized(exc_info.value)

    messages = {item["field"]: item["message"] for item in data["errors"]}
    assert messages["email"] == "Email không đúng định dạng."
    assert messages["full_name"] == "Họ và tên phải có ít nhất 2 ký tự."


def test_free_text_limits_match_the_frontend_contract() -> None:
    with pytest.raises(ValidationError) as trip_error:
        CreateTripRequest(
            title="Hà Nội",
            destination="Hà Nội",
            start_date=dt.date(2027, 1, 1),
            end_date=dt.date(2027, 1, 2),
            preferences="x" * 1501,
        )
    with pytest.raises(ValidationError) as activity_error:
        CreateActivityRequest(title="Tham quan", description="x" * 3001, notes="x" * 1001)

    assert {item["loc"][-1] for item in trip_error.value.errors()} == {"preferences"}
    assert {item["loc"][-1] for item in activity_error.value.errors()} == {"description", "notes"}


def test_profile_and_login_limits_reject_invalid_values() -> None:
    with pytest.raises(ValidationError) as profile_error:
        UserPreferences(phone="abc", bio="x" * 1001)
    with pytest.raises(ValidationError) as login_error:
        LoginRequest(login="valid-user", password="x" * 129)

    assert {item["loc"][-1] for item in profile_error.value.errors()} == {"phone", "bio"}
    assert {item["loc"][-1] for item in login_error.value.errors()} == {"password"}
