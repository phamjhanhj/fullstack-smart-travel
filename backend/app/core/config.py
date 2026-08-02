"""
Cấu hình tập trung của ứng dụng.
Đọc biến môi trường từ file .env thông qua pydantic-settings.
"""
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/smart_travel"
    ENVIRONMENT: str = "development"

    # JWT
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "smart-travel-api"
    JWT_AUDIENCE: str = "smart-travel-web"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 900
    REFRESH_TOKEN_EXPIRE_SECONDS: int = 604800
    REFRESH_COOKIE_NAME: str = "smart_travel_refresh"
    REFRESH_COOKIE_SECURE: bool = False

    # Groq AI
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_ITINERARY_TEMPERATURE: float = 0.2
    GROQ_MAX_RETRIES: int = 0

    # Hard budgets for synchronous itinerary generation.
    ITINERARY_TOTAL_TIMEOUT_SECONDS: float = 55.0
    ITINERARY_GROQ_TIMEOUT_SECONDS: float = 23.0
    ITINERARY_MAX_AI_CALLS: int = 1
    ITINERARY_MAX_CANDIDATES_SHORT: int = 24
    ITINERARY_MAX_CANDIDATES_LONG: int = 32
    ITINERARY_ONLINE_FALLBACK: bool = False

    # Route verification. "haversine" is offline and deterministic; "osrm"
    # uses OSRM first and falls back to Haversine when unavailable.
    ROUTING_PROVIDER: str = "haversine"
    OSRM_BASE_URL: str = "https://router.project-osrm.org"

    # Google Places
    GOOGLE_PLACES_API_KEY: str = ""

    # Foursquare Places (destination photos)
    FOURSQUARE_API_KEY: str = ""

    # CORS — danh sách domain được phép gọi API, phân tách bởi dấu phẩy
    ALLOWED_ORIGINS: str = "http://localhost:4200,http://100.110.155.58:4200,http://127.0.0.1:4200"
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,testserver,100.110.155.58"

    ADMIN_EMAILS: str = "phanh12012004@gmail.com"

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_AI_PER_MINUTE: int = 12
    RATE_LIMIT_SEARCH_PER_MINUTE: int = 60
    RATE_LIMIT_PHOTO_PER_MINUTE: int = 40
    TRUST_PROXY_HEADERS: bool = False
    TRUSTED_PROXY_CIDRS: str = "127.0.0.1/32,::1/128"

    EXTERNAL_HTTP_TIMEOUT_SECONDS: float = 10.0
    MAX_REQUEST_BODY_BYTES: int = 2_000_000

    # Transactional email (Gmail SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USE_TLS: bool = True
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Smart Travel PKA"
    FRONTEND_BASE_URL: str = "http://localhost:4200"

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        env = self.ENVIRONMENT.lower().strip()
        if env not in {"development", "test", "testing", "production", "prod"}:
            raise ValueError("ENVIRONMENT must be development, test, or production")
        weak_secrets = {
            "dev-secret-key-change-in-production",
            "change-this-to-a-random-secret-key-in-production",
            "docker-dev-secret-change-before-production",
            "secret",
            "password",
        }
        if self.JWT_ALGORITHM != "HS256":
            raise ValueError("JWT_ALGORITHM must be HS256")
        if env in {"production", "prod"} and (
            self.JWT_SECRET_KEY in weak_secrets or len(self.JWT_SECRET_KEY) < 32
        ):
            raise ValueError("JWT_SECRET_KEY must be a random value of at least 32 characters in production")
        if env in {"production", "prod"} and not self.REFRESH_COOKIE_SECURE:
            raise ValueError("REFRESH_COOKIE_SECURE must be enabled in production")
        if env in {"production", "prod"} and any(
            marker in self.DATABASE_URL for marker in ("postgres:password@", "smart_travel:smart_travel_local_only@")
        ):
            raise ValueError("DATABASE_URL must not use a development password in production")
        if "*" in self.allowed_origins_list:
            raise ValueError("Wildcard CORS origins are not allowed when credentials are enabled")
        for origin in self.allowed_origins_list:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
                raise ValueError(f"Invalid CORS origin: {origin}")
            if env in {"production", "prod"} and parsed.scheme != "https":
                raise ValueError("Production CORS origins must use HTTPS")
        frontend_url = urlsplit(self.FRONTEND_BASE_URL)
        if (
            frontend_url.scheme not in {"http", "https"}
            or not frontend_url.netloc
            or frontend_url.path not in {"", "/"}
            or frontend_url.query
            or frontend_url.fragment
        ):
            raise ValueError("FRONTEND_BASE_URL must be an http or https origin without a path")
        if env in {"production", "prod"} and frontend_url.scheme != "https":
            raise ValueError("FRONTEND_BASE_URL must use HTTPS in production")
        if env in {"production", "prod"} and "*" in self.allowed_hosts_list:
            raise ValueError("Wildcard hosts are not allowed in production")
        if not 1_024 <= self.MAX_REQUEST_BODY_BYTES <= 10_000_000:
            raise ValueError("MAX_REQUEST_BODY_BYTES must be between 1024 and 10000000")
        if not 300 <= self.ACCESS_TOKEN_EXPIRE_SECONDS <= 86_400:
            raise ValueError("ACCESS_TOKEN_EXPIRE_SECONDS must be between 300 and 86400")
        if not self.ACCESS_TOKEN_EXPIRE_SECONDS < self.REFRESH_TOKEN_EXPIRE_SECONDS <= 2_678_400:
            raise ValueError("REFRESH_TOKEN_EXPIRE_SECONDS must be longer than access tokens and at most 31 days")
        if min(
            self.RATE_LIMIT_AUTH_PER_MINUTE,
            self.RATE_LIMIT_AI_PER_MINUTE,
            self.RATE_LIMIT_SEARCH_PER_MINUTE,
            self.RATE_LIMIT_PHOTO_PER_MINUTE,
        ) < 1:
            raise ValueError("Rate limits must be positive")
        return self

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def admin_email_set(self) -> set[str]:
        return {email.strip().lower() for email in self.ADMIN_EMAILS.split(",") if email.strip()}

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower().strip() in {"production", "prod"}

    @property
    def database_url_async(self) -> str:
        """
        Tự động chuyển đổi postgresql:// thành postgresql+asyncpg:// nếu người dùng quên điền driver asyncpg.
        """
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url



@lru_cache
def get_settings() -> Settings:
    """Cache settings — chỉ đọc file .env một lần duy nhất."""
    return Settings()


settings = get_settings()
