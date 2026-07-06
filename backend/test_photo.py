import asyncio
from app.db.session import AsyncSessionLocal
from app.services.destination_photo_service import get_destination_photos

async def main():
    async with AsyncSessionLocal() as db:
        print("Testing with Đà Nẵng...")
        res1 = await get_destination_photos(db, "Đà Nẵng", 3)
        print("Đà Nẵng Result:", res1)
        
        print("\nTesting with Hà Nội...")
        res2 = await get_destination_photos(db, "Hà Nội", 3)
        print("Hà Nội Result:", res2)

        print("\nTesting with Sapa...")
        res3 = await get_destination_photos(db, "Sapa", 2)
        print("Sapa Result:", res3)

        print("\nTesting cache hit for Đà Nẵng (should say source: cache)...")
        res_cache = await get_destination_photos(db, "Đà Nẵng", 3)
        print("Đà Nẵng Cache Result:", res_cache)

if __name__ == "__main__":
    asyncio.run(main())
