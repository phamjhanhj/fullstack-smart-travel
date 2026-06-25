"""
Entry point cua ung dung FastAPI.
Khoi tao app, dang ky middleware CORS, exception handlers, va toan bo 32 endpoints
duoc chia theo 7 module dung yeu cau (Auth, Users, Trips, Day Plans & Activities,
Locations, Budget, AI Chat & Suggestions). Chat suggestions extraction prompt added.
"""
from __future__ import annotations

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

app = FastAPI(
    title="Smart Travel Planner API",
    description="API cho he thong goi y dia diem va lap lich trinh du lich thong minh tich hop AI",
    version="1.0.0",
)

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


@app.get("/")
async def root():
    return {"service": "Smart Travel Planner API", "status": "running", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
