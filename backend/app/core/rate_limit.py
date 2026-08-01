from __future__ import annotations

import hashlib
import ipaddress
import time
import uuid
from collections.abc import Callable

from fastapi import Request
from sqlalchemy import text

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import JWTError, decode_token
from app.db.session import AsyncSessionLocal


def _trusted_proxy(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
        networks = (
            ipaddress.ip_network(value.strip(), strict=False)
            for value in settings.TRUSTED_PROXY_CIDRS.split(",")
            if value.strip()
        )
        return any(address in network for network in networks)
    except ValueError:
        return False


def _verified_credential_identity(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    scheme, separator, token = authorization.partition(" ")
    token = token.strip()
    if separator != " " or scheme.lower() != "bearer" or not token or len(token) > 4096:
        return "anonymous"
    try:
        payload = decode_token(token)
        if payload.get("type") not in {"access", "refresh"}:
            return "anonymous"
        subject = str(uuid.UUID(payload["sub"]))
    except (JWTError, KeyError, ValueError):
        return "anonymous"
    return f"user:{subject}"


def _client_key(request: Request, scope: str) -> str:
    """Build a non-reversible key without storing raw credentials."""
    host = request.client.host if request.client else "unknown"
    if settings.TRUST_PROXY_HEADERS and _trusted_proxy(host):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            candidate = forwarded.split(",")[0].strip()
            try:
                host = str(ipaddress.ip_address(candidate))
            except ValueError:
                pass
    identity = _verified_credential_identity(request)
    return hashlib.sha256(f"{scope}:{host}:{identity}".encode("utf-8")).hexdigest()


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
