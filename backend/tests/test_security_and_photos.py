from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
import uuid

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.core.config import Settings
from app.core.exceptions import AppError
from app.main import RequestBodyLimitMiddleware
from app.core.rate_limit import _client_key
from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_and_update_password,
    verify_password,
)
from app.schemas.day_plan import CreateActivityRequest, GenerateDaysRequest, UpdateActivityRequest
from app.schemas.budget import CreateBudgetItemRequest
from app.schemas.location import UpsertLocationRequest
from app.schemas.p1_features import JournalCreate
from app.schemas.p2_features import CommentCreate
from app.schemas.trip import CreateTripRequest, UpdateTripRequest
from app.schemas.user import UpdateProfileRequest
from app.services import budget_service, trip_service
from app.services.destination_photo_service import _build_photo_details
from app.services.trip_history_service import diff_snapshots, serialize_value


def test_production_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="dev-secret-key-change-in-production",
            REFRESH_COOKIE_SECURE=True,
            ALLOWED_ORIGINS="http://localhost:4200",
        )


def test_cors_rejects_wildcard_origin() -> None:
    with pytest.raises(ValidationError):
        Settings(ALLOWED_ORIGINS="*")


def test_production_requires_secure_refresh_cookie() -> None:
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="a-random-production-secret-that-is-long-enough-123",
            DATABASE_URL="postgresql+asyncpg://app:unique-password@db:5432/app",
            ALLOWED_ORIGINS="https://travel.example.com",
            ALLOWED_HOSTS="travel.example.com",
            REFRESH_COOKIE_SECURE=False,
        )


def test_production_requires_https_origins() -> None:
    with pytest.raises(ValidationError, match="Production CORS origins must use HTTPS"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="a-random-production-secret-that-is-long-enough-123",
            DATABASE_URL="postgresql+asyncpg://app:unique-password@db:5432/app",
            ALLOWED_ORIGINS="http://travel.example.com",
            ALLOWED_HOSTS="travel.example.com",
            FRONTEND_BASE_URL="https://travel.example.com",
            REFRESH_COOKIE_SECURE=True,
        )


def _request(authorization: str | None = None, *, client_host: str = "127.0.0.1", forwarded_for: str | None = None) -> Request:
    headers = [] if authorization is None else [(b"authorization", authorization.encode())]
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "query_string": b"",
            "headers": headers,
            "client": (client_host, 5000),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def test_jwt_tokens_are_unique_and_require_verified_claims() -> None:
    user_id = str(uuid.uuid4())
    first = create_access_token(user_id)
    second = create_access_token(user_id)

    assert first != second
    payload = decode_token(first)
    assert payload["sub"] == user_id
    assert payload["type"] == "access"
    assert payload["jti"]


def test_new_password_hashes_preserve_characters_after_bcrypt_limit() -> None:
    password = "a" * 80
    hashed = hash_password(password)

    assert hashed.startswith("$bcrypt-sha256$")
    assert verify_password(password, hashed)
    assert not verify_password("a" * 72 + "b" * 8, hashed)


def test_legacy_bcrypt_hash_is_upgraded_after_successful_verification() -> None:
    from passlib.context import CryptContext

    password = "legacy-password"
    legacy_hash = CryptContext(schemes=["bcrypt"]).hash(password)
    valid, upgraded_hash = verify_and_update_password(password, legacy_hash)

    assert valid is True
    assert upgraded_hash is not None
    assert upgraded_hash.startswith("$bcrypt-sha256$")
    assert verify_password(password, upgraded_hash)


def test_rate_limit_ignores_unverified_authorization_variations() -> None:
    first = _client_key(_request("Bearer invalid-one"), "search")
    second = _client_key(_request("Bearer invalid-two"), "search")
    assert first == second

    user_id = str(uuid.uuid4())
    valid_one = _client_key(_request(f"Bearer {create_access_token(user_id)}"), "search")
    valid_two = _client_key(_request(f"Bearer {create_access_token(user_id)}"), "search")
    assert valid_one == valid_two
    assert valid_one != first


def test_rate_limit_only_accepts_forwarded_ip_from_trusted_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(rate_limit_module.settings, "TRUSTED_PROXY_CIDRS", "127.0.0.1/32")

    trusted_first = _client_key(_request(forwarded_for="203.0.113.10"), "search")
    trusted_second = _client_key(_request(forwarded_for="203.0.113.11"), "search")
    assert trusted_first != trusted_second

    untrusted_first = _client_key(
        _request(client_host="198.51.100.5", forwarded_for="203.0.113.10"),
        "search",
    )
    untrusted_second = _client_key(
        _request(client_host="198.51.100.5", forwarded_for="203.0.113.11"),
        "search",
    )
    assert untrusted_first == untrusted_second


def test_url_fields_require_http_or_https() -> None:
    with pytest.raises(ValidationError):
        UpdateProfileRequest(avatar_url="javascript:alert(1)")

    with pytest.raises(ValidationError):
        UpdateTripRequest(cover_image_url="ftp://example.com/image.jpg")

    with pytest.raises(ValidationError):
        UpdateActivityRequest(booking_url="javascript:alert(1)")

    with pytest.raises(ValidationError):
        JournalCreate(entry_date=date.today(), photo_urls=["javascript:alert(1)"])

    with pytest.raises(ValidationError):
        UpdateTripRequest(cover_image_url="https://")

    with pytest.raises(ValidationError):
        UpdateActivityRequest(booking_url="https://user:password@example.com/book")


def test_activity_time_range_and_update_title_are_validated() -> None:
    with pytest.raises(ValidationError):
        CreateActivityRequest(title="Lunch", start_time="12:00", end_time="11:30")

    with pytest.raises(ValidationError):
        UpdateActivityRequest(title="")


def test_trip_update_fields_are_validated() -> None:
    with pytest.raises(ValidationError):
        UpdateTripRequest(title="")

    with pytest.raises(ValidationError):
        UpdateTripRequest(
            start_date=date(2026, 8, 2),
            end_date=date(2026, 8, 1),
        )


def test_required_text_rejects_whitespace_and_nested_ai_text_is_bounded() -> None:
    with pytest.raises(ValidationError):
        CreateTripRequest(
            title="   ",
            destination="Da Nang",
            start_date=date(2026, 8, 2),
            end_date=date(2026, 8, 3),
        )

    with pytest.raises(ValidationError):
        CommentCreate(content="   ")

    with pytest.raises(ValidationError):
        GenerateDaysRequest(must_visit=["x" * 201])

    with pytest.raises(ValidationError):
        GenerateDaysRequest(interest_weights={f"interest-{index}": 1 for index in range(21)})

    with pytest.raises(ValidationError):
        GenerateDaysRequest(interest_weights={"food": 11})

    with pytest.raises(ValidationError):
        CreateBudgetItemRequest(
            category="food",
            label="Lunch",
            participants=["   "],
        )

    with pytest.raises(ValidationError):
        UpdateProfileRequest(preferences_json="not-json")


def test_location_photo_url_rejects_unsupported_scheme() -> None:
    with pytest.raises(ValidationError):
        UpsertLocationRequest(name="Test", photo_url="javascript:alert(1)")

    with pytest.raises(ValidationError):
        UpsertLocationRequest(name="Test", photo_url="/assets/../private.txt")


@pytest.mark.asyncio
async def test_request_body_limit_counts_streamed_chunks() -> None:
    chunks = iter(
        [
            {"type": "http.request", "body": b"123456", "more_body": True},
            {"type": "http.request", "body": b"789012", "more_body": False},
        ]
    )

    async def receive():
        return next(chunks)

    sent_messages: list[dict] = []

    async def send(message):
        sent_messages.append(message)

    async def downstream(_scope, limited_receive, _send):
        await limited_receive()
        await limited_receive()

    middleware = RequestBodyLimitMiddleware(downstream, max_body_size=10)
    await middleware({"type": "http", "path": "/api/test", "headers": []}, receive, send)

    response_start = next(message for message in sent_messages if message["type"] == "http.response.start")
    assert response_start["status"] == 413


@pytest.mark.asyncio
async def test_group_split_uses_num_travelers(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = SimpleNamespace(full_name="Chủ chuyến đi", email="owner@example.com")

    class FakeResult:
        def scalar_one_or_none(self):
            return owner

    class FakeDb:
        async def execute(self, _statement):
            return FakeResult()

    async def fake_share_state(_db, _trip_id):
        return [], []

    async def fake_budget_items(_db, _trip_id, category=None):
        return [SimpleNamespace(
            actual_amount=900_000,
            planned_amount=1_200_000,
            paid_by=None,
            participants=None,
        )]

    monkeypatch.setattr(budget_service.trip_share_service, "list_share_state", fake_share_state)
    monkeypatch.setattr(budget_service, "list_budget_items", fake_budget_items)
    trip = SimpleNamespace(id="trip-1", user_id="owner-1", num_travelers=3)

    result = await budget_service.get_group_split_summary(FakeDb(), trip)

    assert result["companions_count"] == 3
    assert result["per_person_actual"] == 300_000
    assert result["per_person_planned"] == 400_000
    assert sum(item["net_balance"] for item in result["members_summary"]) == 0


@pytest.mark.asyncio
async def test_trip_update_rejects_invalid_merged_dates() -> None:
    trip = SimpleNamespace(
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 3),
        status="draft",
    )

    with pytest.raises(AppError) as exc_info:
        await trip_service.update_trip(
            None,
            trip,
            UpdateTripRequest(start_date=date(2026, 8, 4)),
            SimpleNamespace(id="user-1"),
        )

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_trip_cannot_complete_before_end_date() -> None:
    trip = SimpleNamespace(
        start_date=date.today(),
        end_date=date.today() + timedelta(days=1),
        status="active",
    )

    with pytest.raises(AppError) as exc_info:
        await trip_service.update_trip(
            None,
            trip,
            UpdateTripRequest(status="completed"),
            SimpleNamespace(id="user-1"),
        )

    assert exc_info.value.status_code == 422


def test_photo_details_are_backward_compatible_metadata() -> None:
    details = _build_photo_details("Da Nang", ["https://example.com/photo.jpg"], "foursquare")

    assert details[0]["url"] == "https://example.com/photo.jpg"
    assert details[0]["thumbnail_url"] == "https://example.com/photo.jpg"
    assert details[0]["source"] == "foursquare"
    assert details[0]["alt"] == "Travel photo of Da Nang"


def test_trip_history_diff_uses_labels_and_changed_values_only() -> None:
    changes = diff_snapshots(
        {"title": "Old trip", "budget": 1000, "status": "draft"},
        {"title": "New trip", "budget": 1000, "status": "active"},
        {"title": "Ten chuyen di", "status": "Trang thai"},
    )

    assert changes == [
        {"field": "title", "label": "Ten chuyen di", "before": "Old trip", "after": "New trip"},
        {"field": "status", "label": "Trang thai", "before": "draft", "after": "active"},
    ]


def test_trip_history_serialize_value_handles_nested_values() -> None:
    payload = serialize_value({"items": [{"id": "abc", "value": None}]})

    assert payload == {"items": [{"id": "abc", "value": None}]}
