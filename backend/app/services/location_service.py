"""
Business logic - Module 5: Locations.
Dung OpenStreetMap (Nominatim cho text search, Overpass cho nearby search)
thay cho Google Places - khong can API key, hoan toan mien phi.
"""
from __future__ import annotations

import math
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Location
from app.schemas.location import UpsertLocationRequest

_NOMINATIM_URL = "https://nominatim.openstreetmap.org"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_HEADERS = {"User-Agent": "SmartTravelPlannerBackend/1.0"}


# --- Text Search (GET /locations/search) ------------------------------------

async def search_locations(db: AsyncSession, query: str, destination: str | None, limit: int) -> list[dict]:
    """
    Tim kiem theo tu khoa qua Nominatim, sau do upsert ket qua vao DB
    (giong tinh chat "backend goi Google Places API va upsert" trong spec goc,
    chi khac nguon du lieu la OpenStreetMap).
    """
    full_query = f"{query} {destination}".strip() if destination else query

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{_NOMINATIM_URL}/search",
            params={
                "q": full_query,
                "format": "json",
                "limit": limit,
                "addressdetails": 1,
                "accept-language": "vi",
            },
            headers=_HEADERS,
        )
        resp.raise_for_status()
        raw_results = resp.json()

    saved_locations = []
    for place in raw_results:
        osm_place_id = f"osm_{place['osm_type'][0].upper()}{place['osm_id']}"
        location = await _upsert_location(
            db,
            name=_extract_name(place),
            address=place.get("display_name"),
            lat=float(place["lat"]),
            lng=float(place["lon"]),
            category=_map_osm_type(place.get("type", ""), place.get("class", "")),
            google_place_id=osm_place_id,
            photo_url=None,
            rating=None,
        )
        saved_locations.append(location)

    return saved_locations


# --- Detail (GET /locations/{id}) --------------------------------------------

async def get_location_or_404(db: AsyncSession, location_id: uuid.UUID) -> Location:
    from app.core.exceptions import NotFoundError

    result = await db.execute(select(Location).where(Location.id == location_id))
    location = result.scalar_one_or_none()
    if location is None:
        raise NotFoundError("Khong tim thay dia diem nay")
    return location


# --- Nearby Search (GET /locations/nearby) -----------------------------------

async def search_nearby(
    db: AsyncSession, lat: float, lng: float, radius: int, category: str | None
) -> list[dict]:
    """Tim dia diem gan toa do qua Overpass API, tinh khoang cach bang Haversine."""
    osm_filter = _category_to_overpass_filter(category)
    overpass_query = f"""
    [out:json][timeout:15];
    (
      node{osm_filter}(around:{radius},{lat},{lng});
      way{osm_filter}(around:{radius},{lat},{lng});
    );
    out center 20;
    """

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(_OVERPASS_URL, data={"data": overpass_query}, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        name = tags.get("name")
        if not name:
            continue

        if element["type"] == "way":
            place_lat = element.get("center", {}).get("lat", lat)
            place_lng = element.get("center", {}).get("lon", lng)
        else:
            place_lat = element.get("lat", lat)
            place_lng = element.get("lon", lng)

        osm_place_id = f"osm_{element['type'][0].upper()}{element['id']}"
        cat = _map_osm_tags(tags)

        location = await _upsert_location(
            db,
            name=name,
            address=_build_address_from_tags(tags),
            lat=place_lat,
            lng=place_lng,
            category=cat,
            google_place_id=osm_place_id,
            photo_url=None,
            rating=None,
        )

        results.append({
            **{c.name: getattr(location, c.name) for c in location.__table__.columns},
            "distance_meters": int(_haversine(lat, lng, place_lat, place_lng)),
        })

    results.sort(key=lambda x: x["distance_meters"])
    return results


# --- Upsert (POST /locations) -------------------------------------------------

async def upsert_location_from_request(db: AsyncSession, payload: UpsertLocationRequest) -> tuple[Location, bool]:
    """Tra ve (location, created) - created=True neu vua tao moi, False neu da ton tai."""
    if payload.google_place_id:
        existing = await db.execute(
            select(Location).where(Location.google_place_id == payload.google_place_id)
        )
        found = existing.scalar_one_or_none()
        if found is not None:
            return found, False

    location = Location(**payload.model_dump())
    db.add(location)
    await db.commit()
    await db.refresh(location)
    return location, True


async def _upsert_location(db: AsyncSession, *, google_place_id: str, **fields) -> Location:
    """Helper noi bo - upsert theo google_place_id, dung cho search/nearby."""
    existing = await db.execute(select(Location).where(Location.google_place_id == google_place_id))
    location = existing.scalar_one_or_none()

    if location is not None:
        return location

    location = Location(google_place_id=google_place_id, **fields)
    db.add(location)
    await db.commit()
    await db.refresh(location)
    return location


# --- Helpers -------------------------------------------------------------------

def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _category_to_overpass_filter(category: str | None) -> str:
    mapping = {
        "restaurant": '["amenity"~"restaurant|fast_food|bar|bakery"]',
        "cafe": '["amenity"="cafe"]',
        "hotel": '["tourism"~"hotel|hostel|guest_house|motel"]',
        "attraction": '["tourism"~"attraction|museum|artwork|viewpoint|theme_park|zoo"]',
    }
    return mapping.get(category or "", '["amenity"~"restaurant|cafe|hotel|museum|attraction"]')


def _extract_name(place: dict) -> str:
    display = place.get("display_name", "")
    return display.split(",")[0].strip() if display else "Khong ro ten"


def _build_address_from_tags(tags: dict) -> str | None:
    parts = [v for k, v in tags.items() if k in ("addr:housenumber", "addr:street", "addr:city", "addr:district") and v]
    return ", ".join(parts) if parts else tags.get("addr:full")


def _map_osm_type(osm_type: str, osm_class: str) -> str:
    t = osm_type.lower()
    if t in {"restaurant", "fast_food", "bar", "bakery"}:
        return "restaurant"
    if t == "cafe":
        return "cafe"
    if t in {"hotel", "hostel", "guest_house", "motel", "resort"}:
        return "hotel"
    if t in {"attraction", "museum", "artwork", "viewpoint", "theme_park", "zoo"}:
        return "attraction"
    return "other"


def _map_osm_tags(tags: dict) -> str:
    amenity = tags.get("amenity", "")
    tourism = tags.get("tourism", "")
    combined = f"{amenity} {tourism}".lower()
    if amenity == "cafe":
        return "cafe"
    if any(k in combined for k in ["restaurant", "fast_food", "bar", "bakery"]):
        return "restaurant"
    if any(k in combined for k in ["hotel", "hostel", "guest_house", "motel"]):
        return "hotel"
    if any(k in combined for k in ["museum", "attraction", "viewpoint", "zoo"]):
        return "attraction"
    return "other"
