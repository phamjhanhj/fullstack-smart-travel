"""Script test thủ công kết nối Foursquare API — không commit key thật."""
import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


async def test():
    api_key = os.getenv("FOURSQUARE_API_KEY")
    if not api_key:
        print("Chưa có FOURSQUARE_API_KEY trong .env")
        return

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.foursquare.com/v3/places/search",
            params={"query": "Da Nang", "limit": 1},
            headers={"Authorization": api_key, "Accept": "application/json"},
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                print("Thành công:", results[0].get("name"))


if __name__ == "__main__":
    asyncio.run(test())
