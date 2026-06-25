"""
Khởi tạo async engine + session factory cho SQLAlchemy.
Dependency get_db() được dùng trong toàn bộ routers để inject session per-request.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url_async, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class cho toàn bộ ORM models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — tạo 1 session mới cho mỗi request, tự đóng khi xong."""
    async with AsyncSessionLocal() as session:
        yield session
