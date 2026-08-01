from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.routers import auth_router
from app.main import app
from app.schemas.auth import LoginRequest


def test_api_adds_security_headers_and_sanitizes_request_id() -> None:
    client = TestClient(app)
    supplied = "x" * 200
    response = client.get("/health", headers={"x-request-id": supplied})

    assert response.status_code == 200
    assert response.headers["x-request-id"] != supplied
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_trusted_host_rejects_unconfigured_host() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"host": "attacker.example"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_returns_refresh_only_as_httponly_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(
        id=uuid.uuid4(),
        username="traveler",
        email="traveler@example.com",
        full_name="Traveler",
        avatar_url=None,
    )

    async def authenticate(_db, _login, _password):
        return user

    async def issue(_db, _user_id):
        return "access-token", "refresh-token-value-that-is-long-enough"

    monkeypatch.setattr(auth_router.auth_service, "authenticate_user", authenticate)
    monkeypatch.setattr(auth_router.auth_service, "issue_tokens", issue)

    response = await auth_router.login(LoginRequest(login="traveler", password="password"), None)
    payload = json.loads(response.body)
    cookie = response.headers["set-cookie"].lower()

    assert payload["data"]["access_token"] == "access-token"
    assert "refresh_token" not in payload["data"]
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/api/auth" in cookie
