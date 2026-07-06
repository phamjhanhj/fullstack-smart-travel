import asyncio
from app.db.session import AsyncSessionLocal
from app.models.destination_photo import DestinationPhoto
from sqlalchemy import delete

async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(DestinationPhoto))
        await db.commit()
        print("Cleared cache.")

if __name__ == "__main__":
    asyncio.run(main())
