import asyncio
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.session import AsyncSessionLocal
from app.models.public_trip import PublicTripPublication
from app.services import public_trip_service
from app.schemas.public_trip import PublicTripResponse

async def test_payload():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PublicTripPublication)
            .where(
                PublicTripPublication.slug == "lich-trinh-quan-lan-3-ngay-2-dem-chi-tiet",
                PublicTripPublication.status == "published",
                PublicTripPublication.moderation_status == "approved",
            )
            .options(selectinload(PublicTripPublication.author))
        )
        pub = result.scalar_one_or_none()
        print("Found pub ID:", pub.id)
        pub.view_count += 1
        await db.flush() # Flush instead of commit so attributes don't expire
        payload = public_trip_service.publication_payload(pub, public_view=True)
        print("Payload title:", payload.get("title"))
        resp = PublicTripResponse(**payload)
        print("Validated PublicTripResponse SUCCESS!")

if __name__ == "__main__":
    asyncio.run(test_payload())
