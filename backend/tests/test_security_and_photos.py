from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.trip import UpdateTripRequest
from app.schemas.user import UpdateProfileRequest
from app.services.destination_photo_service import _build_photo_details


def test_production_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="dev-secret-key-change-in-production",
            ALLOWED_ORIGINS="http://localhost:4200",
        )


def test_cors_rejects_wildcard_origin() -> None:
    with pytest.raises(ValidationError):
        Settings(ALLOWED_ORIGINS="*")


def test_url_fields_require_http_or_https() -> None:
    with pytest.raises(ValidationError):
        UpdateProfileRequest(avatar_url="javascript:alert(1)")

    with pytest.raises(ValidationError):
        UpdateTripRequest(cover_image_url="ftp://example.com/image.jpg")


def test_photo_details_are_backward_compatible_metadata() -> None:
    details = _build_photo_details("Da Nang", ["https://example.com/photo.jpg"], "foursquare")

    assert details[0]["url"] == "https://example.com/photo.jpg"
    assert details[0]["thumbnail_url"] == "https://example.com/photo.jpg"
    assert details[0]["source"] == "foursquare"
    assert details[0]["alt"] == "Travel photo of Da Nang"
