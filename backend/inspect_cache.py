import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.destination_photo import DestinationPhoto

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(DestinationPhoto))
        rows = res.scalars().all()
        print(f"Total cached rows: {len(rows)}")
        for r in rows:
            print(f"- {r.destination_key}: {r.photo_urls} (Source: {r.source}, Fetched: {r.fetched_at})")

if __name__ == "__main__":
    asyncio.run(main())
