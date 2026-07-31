from __future__ import annotations

import hashlib
import time
from collections.abc import Callable

from fastapi import Request
from sqlalchemy import text

from app.core.config import settings
from app.core.exceptions import AppError
from app.db.session import AsyncSessionLocal


def _client_key(request: Request, scope: str) -> str:
    """Build a non-reversible key without storing raw credentials."""
    host = request.client.host if request.client else "unknown"
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            host = forwarded.split(",")[0].strip()
    authorization = request.headers.get("authorization", "")
    credential_hint = hashlib.sha256(authorization.encode("utf-8")).hexdigest() if authorization else "anonymous"
    return hashlib.sha256(f"{scope}:{host}:{credential_hint}".encode("utf-8")).hexdigest()


def rate_limit(scope: str, max_requests: int, window_seconds: int = 60) -> Callable:
    async def dependency(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        now = int(time.time())
        window_start = now - (now % window_seconds)
        key_hash = _client_key(request, scope)
        async with AsyncSessionLocal() as session:
            count = await session.scalar(
                text("""
                    INSERT INTO api_rate_limit_buckets
                        (scope, key_hash, window_start, request_count, expires_at)
                    VALUES (:scope, :key_hash, :window_start, 1, :expires_at)
                    ON CONFLICT (scope, key_hash, window_start)
                    DO UPDATE SET request_count = api_rate_limit_buckets.request_count + 1
                    RETURNING request_count
                """),
                {
                    "scope": scope,
                    "key_hash": key_hash,
                    "window_start": window_start,
                    "expires_at": window_start + window_seconds * 2,
                },
            )
            # Opportunistic cleanup is bounded to the current request and safe
            # across multiple workers/processes.
            await session.execute(
                text("DELETE FROM api_rate_limit_buckets WHERE expires_at < :now"),
                {"now": now},
            )
            await session.commit()

        if int(count or 0) > max_requests:
            raise AppError("Qua nhieu yeu cau, vui long thu lai sau", status_code=429)

    return dependency