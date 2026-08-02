"""
Entry point cua ung dung FastAPI.
Khoi tao app, dang ky middleware CORS, exception handlers.
"""
from __future__ import annotations

import logging
import re
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.response import envelope

from app.api.routers.auth_router import router as auth_router
from app.api.routers.user_router import router as user_router
from app.api.routers.trip_router import router as trip_router
from app.api.routers.activity_router import trip_days_router, activities_router
from app.api.routers.location_router import router as location_router
from app.api.routers.budget_router import trip_budget_router, budget_items_router
from app.api.routers.chat_router import chat_router, suggestions_trip_router, suggestions_router
from app.api.routers.destination_photo_router import router as destination_photo_router
from app.api.routers.trip_share_router import trip_shares_router, trip_invites_router
from app.api.routers.public_trip_router import public_trips_router, trip_publication_router
from app.api.routers.p1_router import notifications_router, journal_router, collections_router, emergency_router
from app.api.routers.p2_router import router as p2_router

app = FastAPI(
    title="Smart Travel Planner API",
    description="API cho he thong goi y dia diem va lap lich trinh du lich thong minh tich hop AI",
    version="1.0.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

logger = logging.getLogger("app.request")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class RequestBodyLimitMiddleware:
    """Enforce the body limit even when Content-Length is absent or forged."""

    def __init__(self, app, max_body_size: int):
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        received = 0
        exceeded = False

        async def limited_receive():
            nonlocal exceeded, received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_size:
                    exceeded = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def guarded_send(message):
            if not exceeded:
                await send(message)

        await self.app(scope, limited_receive, guarded_send)
        if exceeded:
            path = str(scope.get("path") or "")
            response = envelope(
                data=None,
                message="Du lieu gui len vuot qua gioi han cho phep",
                status_code=413,
            )
            headers = dict(scope.get("headers") or [])
            supplied_id = headers.get(b"x-request-id", b"").decode("ascii", errors="ignore")
            response.headers["X-Request-ID"] = (
                supplied_id if REQUEST_ID_PATTERN.fullmatch(supplied_id) else uuid.uuid4().hex
            )
            _add_security_headers(response, path)
            await response(scope, receive, send)


def _request_id(request) -> str:
    supplied = request.headers.get("x-request-id", "")
    return supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else uuid.uuid4().hex


def _add_security_headers(response, path: str) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"


@app.middleware("http")
async def request_context_middleware(request, call_next):
    """Attach a safe correlation ID and log request failures without payloads."""
    request_id = _request_id(request)
    request.state.request_id = request_id
    path = str(request.scope.get("path") or "")
    started = time.perf_counter()
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            body_size = int(content_length)
        except ValueError:
            body_size = settings.MAX_REQUEST_BODY_BYTES + 1
        if body_size < 0 or body_size > settings.MAX_REQUEST_BODY_BYTES:
            response = envelope(
                data=None,
                message="Du lieu gui len vuot qua gioi han cho phep",
                status_code=413,
            )
            response.headers["X-Request-ID"] = request_id
            _add_security_headers(response, path)
            return response
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled request failure request_id=%s method=%s path=%s",
            request_id,
            request.method,
            path,
        )
        raise
    response.headers["X-Request-ID"] = request_id
    _add_security_headers(response, path)
    if response.status_code >= 500:
        logger.error(
            "Server error request_id=%s method=%s path=%s status=%s duration_ms=%d",
            request_id,
            request.method,
            path,
            response.status_code,
            round((time.perf_counter() - started) * 1000),
        )
    return response

# --- CORS ----------------------------------------------------------------------
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)
app.add_middleware(RequestBodyLimitMiddleware, max_body_size=settings.MAX_REQUEST_BODY_BYTES)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# --- Exception handlers (dam bao moi response dung envelope chuan) -------------
register_exception_handlers(app)

# --- Routers - prefix /api de khop voi Base URL trong spec ---------------------
API_PREFIX = "/api"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(user_router, prefix=API_PREFIX)
app.include_router(trip_router, prefix=API_PREFIX)
app.include_router(trip_days_router, prefix=API_PREFIX)
app.include_router(activities_router, prefix=API_PREFIX)
app.include_router(location_router, prefix=API_PREFIX)
app.include_router(trip_budget_router, prefix=API_PREFIX)
app.include_router(budget_items_router, prefix=API_PREFIX)
app.include_router(chat_router, prefix=API_PREFIX)
app.include_router(suggestions_trip_router, prefix=API_PREFIX)
app.include_router(suggestions_router, prefix=API_PREFIX)
app.include_router(destination_photo_router, prefix=API_PREFIX)
app.include_router(trip_shares_router, prefix=API_PREFIX)
app.include_router(trip_invites_router, prefix=API_PREFIX)
app.include_router(trip_publication_router, prefix=API_PREFIX)
app.include_router(public_trips_router, prefix=API_PREFIX)
app.include_router(notifications_router, prefix=API_PREFIX)
app.include_router(journal_router, prefix=API_PREFIX)
app.include_router(collections_router, prefix=API_PREFIX)
app.include_router(emergency_router, prefix=API_PREFIX)
app.include_router(p2_router, prefix=API_PREFIX)


@app.get("/")
async def root():
    data = {"service": "Smart Travel Planner API", "status": "running"}
    if not settings.is_production:
        data["docs"] = "/docs"
    return data


@app.get("/health")
async def health_check():
    return {"status": "ok"}
