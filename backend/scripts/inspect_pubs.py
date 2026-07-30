import asyncio
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.public_trip import PublicTripPublication

async def inspect():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(PublicTripPublication))
        pubs = res.scalars().all()
        for p in pubs:
            print(f"ID: {p.id} | Slug: '{p.slug}' | Status: '{p.status}' | Moderation: '{p.moderation_status}' | Vis: '{p.visibility}'")

if __name__ == "__main__":
    asyncio.run(inspect())
