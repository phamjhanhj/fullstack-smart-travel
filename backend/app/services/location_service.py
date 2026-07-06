"""
Business logic - Module 5: Locations.
Dung OpenStreetMap (Nominatim cho text search, Overpass cho nearby search)
thay cho Google Places - khong can API key, hoan toan mien phi.
"""
from __future__ import annotations

import math
import unicodedata
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.location import Location
from app.schemas.location import UpsertLocationRequest

_NOMINATIM_URL = "https://nominatim.openstreetmap.org"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_HEADERS = {"User-Agent": "SmartTravelPlannerBackend/1.0"}


async def _enrich_with_photo(db: AsyncSession, location: Location) -> None:
    """Làm giàu kết quả bằng ảnh thật từ Foursquare theo tọa độ."""
    if location.photo_url:
        return

    from app.services.destination_photo_service import get_place_photo_by_coords
    photos = await get_place_photo_by_coords(
        name=location.name,
        lat=location.lat,
        lng=location.lng,
        count=1,
    )
    if photos:
        location.photo_url = photos[0]
        await db.commit()
        await db.refresh(location)


# --- Text Search (GET /locations/search) ------------------------------------

_QUERY_TO_CATEGORY: dict[str, str] = {
    # Vietnamese with diacritics
    "quán ăn": "restaurant", "nhà hàng": "restaurant", "ăn uống": "restaurant",
    "quán ăn ngon": "restaurant", "ẩm thực": "restaurant", "bún": "restaurant",
    "phở": "restaurant", "cơm": "restaurant",
    "cà phê": "cafe", "quán cà phê": "cafe", "cafe": "cafe", "coffee": "cafe",
    "trà sữa": "cafe",
    "khách sạn": "hotel", "lưu trú": "hotel", "nhà nghỉ": "hotel",
    "homestay": "hotel", "hotel": "hotel", "resort": "hotel",
    "tham quan": "attraction", "du lịch": "attraction", "địa điểm du lịch": "attraction",
    "danh lam": "attraction", "thắng cảnh": "attraction", "bảo tàng": "attraction",
    "museum": "attraction", "attraction": "attraction",
    # ASCII (no diacritics) — for users typing without Vietnamese keyboard
    "quan an": "restaurant", "nha hang": "restaurant", "an uong": "restaurant",
    "am thuc": "restaurant", "bun": "restaurant", "pho": "restaurant", "com": "restaurant",
    "ca phe": "cafe", "quan ca phe": "cafe", "tra sua": "cafe",
    "khach san": "hotel", "luu tru": "hotel", "nha nghi": "hotel",
    "tham quan": "attraction", "du lich": "attraction", "dia diem du lich": "attraction",
    "dia diem": "attraction", "danh lam": "attraction", "thang canh": "attraction",
    "bao tang": "attraction",
}


def _guess_category_from_query(query: str) -> str | None:
    """Đoán category từ từ khóa tiếng Việt để dùng filter Overpass chính xác hơn."""
    q = query.lower().strip()
    for keyword, cat in _QUERY_TO_CATEGORY.items():
        if keyword in q:
            return cat
    return None


async def _geocode_destination(destination: str) -> tuple[float, float] | None:
    """Geocode tên thành phố/tỉnh bằng Nominatim, ưu tiên các tiền tố đô thị để ra đúng trung tâm du lịch."""
    queries = []
    dest_lower = destination.lower()
    if not any(k in dest_lower for k in ["thành phố", "thanh pho", "tỉnh", "tinh", "thị xã", "thi xa", "thị trấn", "thi tran", "huyện", "huyen"]):
        queries.append(f"Thành phố {destination}")
        queries.append(f"Thị xã {destination}")
        queries.append(f"Thị trấn {destination}")
    queries.append(destination)

    allowed_classes = {"boundary", "place", "landuse", "natural"}

    for q in queries:
        try:
            async with httpx.AsyncClient(timeout=settings.EXTERNAL_HTTP_TIMEOUT_SECONDS) as client:
                resp = await client.get(
                    f"{_NOMINATIM_URL}/search",
                    params={"q": q, "format": "json", "limit": 5, "accept-language": "vi"},
                    headers=_HEADERS,
                )
                resp.raise_for_status()
                data = resp.json()
                if data:
                    for item in data:
                        if item.get("class") in allowed_classes:
                            return float(item["lat"]), float(item["lon"])
        except Exception as exc:
            print(f"[LocationService] Geocode error for '{q}': {exc}")
    return None


async def search_locations(db: AsyncSession, query: str, destination: str | None, limit: int) -> list[dict]:
    """
    Tìm kiếm địa điểm theo từ khóa + destination.
    Chiến lược 2 bước:
      1. Geocode destination → lấy tọa độ trung tâm
      2. Dùng Overpass API tìm POI thực tế (cafe/nhà hàng/khách sạn...) quanh tọa độ đó
    Nếu không geocode được thì fallback về Nominatim text search cũ.
    """
    # --- Step 1: Xác định category và geocode ---
    category = _guess_category_from_query(query)
    coords = None
    if destination:
        coords = await _geocode_destination(destination)

    # --- Step 2a: Nếu có tọa độ → dùng Overpass tìm POI thật ---
    if coords:
        lat, lng = coords
        # Nếu không đoán được category → mặc định dùng "attraction" thay vì filter quá rộng
        effective_category = category or "attraction"

        for radius in [2000, 5000]:  # Thử 2km trước cho nhanh và tránh timeout, nếu ít kết quả (< 5) thì thử 5km
            overpass_query = _build_overpass_query(effective_category, lat, lng, radius, limit)

            try:
                async with httpx.AsyncClient(timeout=max(settings.EXTERNAL_HTTP_TIMEOUT_SECONDS, 25.0)) as client:
                    resp = await client.post(_OVERPASS_URL, data={"data": overpass_query}, headers=_HEADERS)
                    resp.raise_for_status()
                    data = resp.json()

                saved_locations = []
                for element in data.get("elements", []):
                    if len(saved_locations) >= limit:
                        break

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
                        address=_build_address_from_tags(tags) or f"{destination}",
                        lat=place_lat,
                        lng=place_lng,
                        category=cat,
                        google_place_id=osm_place_id,
                        photo_url=None,
                        rating=None,
                    )
                    if len(saved_locations) < 8:
                        await _enrich_with_photo(db, location)
                    saved_locations.append(location)

                if saved_locations:
                    return saved_locations
                # Nếu không có kết quả, thử bán kính lớn hơn
                print(f"[LocationService] No results with radius={radius}m for '{destination}', expanding...")

            except Exception as exc:
                print(f"[LocationService] Overpass error (radius={radius}): {exc}")
                break  # Nếu lỗi thì fallback luôn, không retry

    # --- Step 2b: Fallback — Nominatim text search (cũ) ---
    full_query = f"{query} {destination}".strip() if destination else query

    async with httpx.AsyncClient(timeout=settings.EXTERNAL_HTTP_TIMEOUT_SECONDS) as client:
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
    for i, place in enumerate(raw_results):
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
        if i < 8:
            await _enrich_with_photo(db, location)
        saved_locations.append(location)

    return saved_locations


async def discover_itinerary_candidates(
    db: AsyncSession,
    destination: str,
    must_visit: list[str] | None = None,
    interests: list[str] | None = None,
    limit_per_query: int = 8,
) -> list[dict]:
    """
    Build a grounded place pool for itinerary generation from free data sources.
    The return shape is JSON-safe so it can be sent directly to the AI prompt.
    """
    must_visit = [p.strip() for p in (must_visit or []) if p and p.strip()]
    interests = [i.strip().lower() for i in (interests or []) if i and i.strip()]

    queries = [
        ("attraction", "dia diem du lich noi tieng"),
        ("attraction", "danh lam thang canh"),
        ("restaurant", "quan an ngon nha hang noi tieng"),
        ("cafe", "cafe quan ca phe dep"),
        ("hotel", "khach san resort luu tru"),
    ]

    if any(i in {"nature", "adventure", "beaches"} for i in interests):
        queries.insert(1, ("attraction", "thang canh tu nhien bai bien nui"))
    if any(i in {"history", "culture"} for i in interests):
        queries.insert(1, ("attraction", "bao tang di tich pho co den chua"))
    if any(i in {"foodie", "cafe"} for i in interests):
        queries.insert(2, ("restaurant", "am thuc dac san dia phuong"))

    raw_locations: list[Location] = []

    for place in must_visit:
        try:
            raw_locations.extend(await search_locations(db, place, destination, 3))
        except Exception as exc:
            print(f"[LocationService] must-visit search failed for '{place}': {exc}")

    for _category, query in queries:
        try:
            raw_locations.extend(await search_locations(db, query, destination, limit_per_query))
        except Exception as exc:
            print(f"[LocationService] candidate search failed for '{query}': {exc}")

    deduped: dict[str, Location] = {}
    for loc in raw_locations:
        if not getattr(loc, "name", None):
            continue
        key = _candidate_key(loc)
        if key not in deduped:
            deduped[key] = loc

    candidates = []
    for loc in deduped.values():
        category = loc.category or "other"
        must_match = _match_requested_place(loc.name, must_visit)
        score = _score_candidate(loc, must_match=must_match)
        candidates.append(
            {
                "ref": "",
                "location_id": str(loc.id),
                "name": loc.name,
                "address": loc.address,
                "lat": loc.lat,
                "lng": loc.lng,
                "category": category,
                "photo_url": loc.photo_url,
                "rating": loc.rating,
                "score": score,
                "must_visit_match": must_match,
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    for idx, item in enumerate(candidates[:80], start=1):
        item["ref"] = f"p{idx}"
    return candidates[:80]


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
    overpass_query = _build_overpass_query(category, lat, lng, radius, 25)

    async with httpx.AsyncClient(timeout=max(settings.EXTERNAL_HTTP_TIMEOUT_SECONDS, 15.0)) as client:
        resp = await client.post(_OVERPASS_URL, data={"data": overpass_query}, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()

    results = []
    idx = 0
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

        if idx < 5:
            await _enrich_with_photo(db, location)
            idx += 1

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


def _build_overpass_query(category: str | None, lat: float, lng: float, radius: int, limit: int) -> str:
    """Xây dựng Overpass QL query với union syntax chuẩn, tránh regex key match không ổn định."""
    tag_filters = {
        "restaurant": [
            '["amenity"~"restaurant|fast_food|food_court|bar|pub|bbq|bistro"]',
        ],
        "cafe": [
            '["amenity"~"cafe|ice_cream"]',
        ],
        "hotel": [
            '["tourism"~"hotel|hostel|guest_house|motel|resort|camp_site"]',
        ],
        "attraction": [
            '["tourism"~"attraction|museum|artwork|viewpoint|theme_park|zoo|aquarium|gallery"]',
            '["historic"~"monument|memorial|castle|ruins|tomb|temple|church|pagoda"]',
            '["leisure"~"park|garden|nature_reserve|water_park"]',
        ],
    }

    filters = tag_filters.get(category or "attraction", tag_filters["attraction"])

    # Xây union query: mỗi filter → 1 cặp node+way
    union_parts = []
    for f in filters:
        union_parts.append(f'  node{f}(around:{radius},{lat},{lng});')
        union_parts.append(f'  way{f}(around:{radius},{lat},{lng});')

    union_body = "\n".join(union_parts)
    return f"""
[out:json][timeout:25];
(
{union_body}
);
out center {limit + 10};
"""


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
    historic = tags.get("historic", "")
    leisure = tags.get("leisure", "")
    shop = tags.get("shop", "")
    cuisine = tags.get("cuisine", "")
    combined = f"{amenity} {tourism} {historic} {leisure} {shop} {cuisine}".lower()
    if amenity in {"cafe", "coffee"} or "coffee" in combined or "tea" in combined or "bubble_tea" in combined:
        return "cafe"
    if any(k in combined for k in ["restaurant", "fast_food", "food_court", "bar", "pub", "bakery", "bbq", "ice_cream"]):
        return "restaurant"
    if any(k in combined for k in ["hotel", "hostel", "guest_house", "motel", "resort", "camp_site", "apartment", "chalet"]):
        return "hotel"
    if any(k in combined for k in ["museum", "attraction", "viewpoint", "zoo", "aquarium", "gallery",
                                    "monument", "memorial", "castle", "ruins", "park", "garden",
                                    "nature_reserve", "water_park", "theme_park"]):
        return "attraction"
    return "other"


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _candidate_key(location: Location) -> str:
    name = _strip_accents(location.name or "").strip()
    if location.lat is not None and location.lng is not None:
        return f"{name}:{round(location.lat, 4)}:{round(location.lng, 4)}"
    return name


def _match_requested_place(name: str, requested_places: list[str]) -> str | None:
    clean_name = _strip_accents(name)
    for place in requested_places:
        clean_place = _strip_accents(place)
        if clean_place and (clean_place in clean_name or clean_name in clean_place):
            return place
    return None


def _score_candidate(location: Location, *, must_match: str | None) -> float:
    score = 10.0
    category = (location.category or "").lower()
    if must_match:
        score += 100
    if category == "attraction":
        score += 35
    elif category in {"restaurant", "cafe"}:
        score += 20
    elif category == "hotel":
        score += 8
    if location.rating:
        score += min(location.rating * 8, 40)
    if location.photo_url:
        score += 6
    if location.lat is not None and location.lng is not None:
        score += 4
    return score
