"""
Cấu hình tập trung của ứng dụng.
Đọc biến môi trường từ file .env thông qua pydantic-settings.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/smart_travel"

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

    # CORS — danh sách domain được phép gọi API, phân tách bởi dấu phẩy
    ALLOWED_ORIGINS: str = "http://localhost:4200"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

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
