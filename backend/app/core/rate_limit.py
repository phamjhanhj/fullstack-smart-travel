from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import AppError

_buckets: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request, scope: str) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    host = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    auth_hint = request.headers.get("authorization", "")
    return f"{scope}:{host}:{hash(auth_hint)}"


def rate_limit(scope: str, max_requests: int, window_seconds: int = 60) -> Callable:
    async def dependency(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        now = time.monotonic()
        key = _client_key(request, scope)
        bucket = _buckets[key]

        while bucket and now - bucket[0] >= window_seconds:
            bucket.popleft()

        if len(bucket) >= max_requests:
            raise AppError("Qua nhieu yeu cau, vui long thu lai sau", status_code=429)

        bucket.append(now)

    return dependency
