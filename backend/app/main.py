"""
Entry point cua ung dung FastAPI.
Khoi tao app, dang ky middleware CORS, exception handlers, va toan bo 32 endpoints
duoc chia theo 7 module dung yeu cau (Auth, Users, Trips, Day Plans & Activities,
Locations, Budget, AI Chat & Suggestions). Chat suggestions extraction prompt added.
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers

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
)

logger = logging.getLogger("app.request")


@app.middleware("http")
async def request_context_middleware(request, call_next):
    """Attach a safe correlation ID and log request failures without payloads."""
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled request failure request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        raise
    response.headers["X-Request-ID"] = request_id
    if response.status_code >= 500:
        logger.error(
            "Server error request_id=%s method=%s path=%s status=%s duration_ms=%d",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            round((time.perf_counter() - started) * 1000),
        )
    return response

# --- CORS ----------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    return {"service": "Smart Travel Planner API", "status": "running", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
