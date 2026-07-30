import asyncio
from dotenv import load_dotenv
load_dotenv()
from app.db.session import AsyncSessionLocal
from app.services import public_trip_service

async def debug():
    async with AsyncSessionLocal() as db:
        pub = await public_trip_service.get_publication_by_slug(db, "lich-trinh-quan-lan-3-ngay-2-dem-chi-tiet")
        await db.refresh(pub)
        print("1. pub loaded")
        try:
            print("2. show_name:", (pub.privacy_options or {}).get("show_author_name", True))
        except Exception as e:
            print("Failed at privacy_options:", e)

        try:
            print("3. author:", pub.author)
        except Exception as e:
            print("Failed at author:", e)

        try:
            print("4. getattr columns:")
            for col in pub.__table__.columns:
                val = getattr(pub, col.name)
                print(f"   col {col.name} ok")
        except Exception as e:
            print("Failed at getattr col:", e)

if __name__ == "__main__":
    asyncio.run(debug())