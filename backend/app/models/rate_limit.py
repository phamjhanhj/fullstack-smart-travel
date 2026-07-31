"""Shared database buckets for API rate limiting."""
from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class ApiRateLimitBucket(Base):
    __tablename__ = "api_rate_limit_buckets"

    scope: Mapped[str] = mapped_column(String(80), primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)