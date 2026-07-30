"""Smoke-test DB-first candidate retrieval after importing the dataset."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.location import Location
from app.services.location_service import (
    discover_itinerary_candidates,
    explore_dataset_locations,
    search_locations_hybrid,
)


async def run(destination: str) -> None:
    async with AsyncSessionLocal() as db:
        total = await db.scalar(
            select(func.count()).select_from(Location).where(Location.source_dataset_id.is_not(None))
        )
        active = await db.scalar(
            select(func.count())
            .select_from(Location)
            .where(Location.source_dataset_id.is_not(None), Location.status == "active")
        )
        candidates = await discover_itinerary_candidates(
            db,
            destination=destination,
            must_visit=[],
            interests=["culture", "foodie"],
        )
        explore = await explore_dataset_locations(
            db,
            destination=destination,
            category="attraction",
            page=1,
            limit=36,
        )
        local_search = await search_locations_hybrid(
            db,
            query="bao tang",
            destination=destination,
            category="attraction",
            limit=10,
            include_external=False,
        )
    print(
        json.dumps(
            {
                "imported_locations": total,
                "active_locations": active,
                "destination": destination,
                "candidate_count": len(candidates),
                "explore_total": explore["total"],
                "explore_first_page": len(explore["items"]),
                "explore_has_more": explore["has_more"],
                "local_search_count": len(local_search),
                "local_search_sample": [item["name"] for item in local_search[:3]],
                "categories": {
                    category: sum(item["category"] == category for item in candidates)
                    for category in ("attraction", "restaurant", "cafe", "hotel")
                },
                "sample": [
                    {
                        "ref": item["ref"],
                        "name": item["name"],
                        "category": item["category"],
                        "confidence": item.get("data_confidence"),
                        "coordinate_status": item.get("coordinate_status"),
                    }
                    for item in candidates[:5]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", default="Đà Nẵng")
    args = parser.parse_args()
    asyncio.run(run(args.destination))


if __name__ == "__main__":
    main()
