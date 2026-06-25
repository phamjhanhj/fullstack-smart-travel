"""
Script tao bang truc tiep tu SQLAlchemy models - dung nhanh cho do an,
khong can setup Alembic migration day du.

Chay: python -m scripts.create_tables
"""
import asyncio

from app.db.session import Base, engine
from app import models  # noqa: F401 - import de dang ky toan bo model vao Base.metadata


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Da tao toan bo bang trong database.")


if __name__ == "__main__":
    asyncio.run(main())
