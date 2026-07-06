import httpx

async def test():
    uas = [
        "SmartTravelPlannerBackend/1.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "SmartTravelPlannerBackend/1.0 (contact@smarttravelplanner.com)"
    ]
    for ua in uas:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "titles": "Đà Nẵng",
                        "prop": "pageimages",
                        "format": "json",
                        "pithumbsize": 600
                    },
                    headers={"User-Agent": ua}
                )
                print(f"UA: {ua[:30]}... -> Status: {resp.status_code}")
                if resp.status_code == 200:
                    print("Data:", resp.json())
        except Exception as e:
            print(f"Error for {ua[:30]}...: {e}")

import asyncio
asyncio.run(test())
