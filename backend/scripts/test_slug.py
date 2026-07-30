import asyncio
from dotenv import load_dotenv
load_dotenv()
from app.db.session import AsyncSessionLocal
from app.services import public_trip_service

async def test_slug_query():
    async with AsyncSessionLocal() as db:
        try:
            pub = await public_trip_service.get_publication_by_slug(db, "lich-trinh-quan-lan-3-ngay-2-dem-chi-tiet")
            print("Successfully retrieved publication by slug!")
            payload = public_trip_service.publication_payload(pub, public_view=True)
            print("Successfully built publication_payload!")
        except Exception as e:
            print("Caught exception:", type(e), e)

if __name__ == "__main__":
    asyncio.run(test_slug_query())
