"""
Cấu hình tập trung của ứng dụng.
Đọc biến môi trường từ file .env thông qua pydantic-settings.
"""
from functools import lru_cache

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
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 3600
    REFRESH_TOKEN_EXPIRE_SECONDS: int = 604800

    # Groq AI
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Google Places
    GOOGLE_PLACES_API_KEY: str = ""

    # Foursquare Places (destination photos)
    FOURSQUARE_API_KEY: str = ""

    # CORS — danh sách domain được phép gọi API, phân tách bởi dấu phẩy
    ALLOWED_ORIGINS: str = "http://localhost:4200"

    ADMIN_EMAILS: str = ""

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_AI_PER_MINUTE: int = 12
    RATE_LIMIT_SEARCH_PER_MINUTE: int = 60
    RATE_LIMIT_PHOTO_PER_MINUTE: int = 40

    EXTERNAL_HTTP_TIMEOUT_SECONDS: float = 10.0

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        env = self.ENVIRONMENT.lower().strip()
        weak_secrets = {
            "dev-secret-key-change-in-production",
            "change-this-to-a-random-secret-key-in-production",
            "secret",
            "password",
        }
        if env in {"production", "prod"} and self.JWT_SECRET_KEY in weak_secrets:
            raise ValueError("JWT_SECRET_KEY must be changed before running in production")
        if "*" in self.allowed_origins_list:
            raise ValueError("Wildcard CORS origins are not allowed when credentials are enabled")
        return self

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def admin_email_set(self) -> set[str]:
        return {email.strip().lower() for email in self.ADMIN_EMAILS.split(",") if email.strip()}

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
