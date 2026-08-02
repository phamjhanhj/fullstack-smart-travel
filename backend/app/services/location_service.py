"""
Business logic - Module 5: Locations.
Dung OpenStreetMap (Nominatim cho text search, Overpass cho nearby search)
thay cho Google Places - khong can API key, hoan toan mien phi.
"""
from __future__ import annotations

import math
from difflib import SequenceMatcher
import unicodedata
import uuid

import httpx
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.location import Location
from app.schemas.location import UpsertLocationRequest
from app.services.province_service import normalize_vietnamese, province_search_names

_NOMINATIM_URL = "https://nominatim.openstreetmap.org"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_HEADERS = {"User-Agent": "SmartTravelPlannerBackend/1.0"}


async def list_supported_destinations(db: AsyncSession) -> list[dict]:
    """Return only dataset namespaces with enough facts for a usable itinerary."""
    result = await db.execute(
        select(Location.province_name, Location.category, func.count(Location.id))
        .where(
            Location.source_dataset_id.is_not(None),
            Location.status == "active",
            Location.province_name.is_not(None),
            Location.coordinate_status.notin_(["suspicious", "missing"]),
        )
        .group_by(Location.province_name, Location.category)
    )
    grouped: dict[str, dict[str, int]] = {}
    for province_name, raw_category, count in result.all():
        if not province_name:
            continue
        category = _scheduler_category(str(raw_category or "other"))
        counts = grouped.setdefault(
            str(province_name),
            {"attraction": 0, "food": 0, "hotel": 0, "total": 0},
        )
        value = int(count or 0)
        counts["total"] += value
        if category == "attraction":
            counts["attraction"] += value
        elif category in {"restaurant", "cafe"}:
            counts["food"] += value
        elif category == "hotel":
            counts["hotel"] += value

    items: list[dict] = []
    for destination, counts in grouped.items():
        can_generate = (
            counts["attraction"] >= 1
            and counts["food"] >= 1
            and counts["hotel"] >= 1
        )
        if not can_generate:
            continue
        items.append(
            {
                "destination": destination,
                "attraction_count": counts["attraction"],
                "food_count": counts["food"],
                "lodging_count": counts["hotel"],
                "total_count": counts["total"],
                "can_generate": True,
            }
        )
    return sorted(items, key=lambda item: normalize_vietnamese(item["destination"]))


def _province_query_names(destination: str) -> list[str]:
    names = province_search_names(destination)
    expanded = list(names)
    if "Thành phố Hồ Chí Minh" in names:
        expanded.extend(["TP. Hồ Chí Minh", "Hồ Chí Minh"])
    if "Bà Rịa - Vũng Tàu" in names:
        expanded.extend(["Bà Rịa – Vũng Tàu", "Bà Rịa Vũng Tàu"])
    if "Kiên Giang" in names or any(k in destination.lower() for k in ["phu quoc", "phú quốc"]):
        expanded.extend(["Kiên Giang", "Phú Quốc", "Thành phố Phú Quốc", "Đảo Phú Quốc"])
    if "Lào Cai" in names or any(k in destination.lower() for k in ["sa pa", "sapa"]):
        expanded.extend(["Lào Cai", "Sa Pa", "Sapa"])
    if "Khánh Hòa" in names or "nha trang" in destination.lower():
        expanded.extend(["Khánh Hòa", "Nha Trang"])
    if "Lâm Đồng" in names or "đà lạt" in destination.lower() or "da lat" in destination.lower():
        expanded.extend(["Lâm Đồng", "Đà Lạt"])
    if "Quảng Ninh" in names or "hạ long" in destination.lower() or "ha long" in destination.lower():
        expanded.extend(["Quảng Ninh", "Hạ Long"])
    return list(dict.fromkeys(expanded))


def _explore_categories(category: str | None) -> list[str]:
    if category in {None, "", "all"}:
        return [
            "attraction", "entertainment", "restaurant", "cafe", "hotel",
            "homestay", "resort", "hostel", "guesthouse",
        ]
    if category in {"meal", "restaurant"}:
        return ["restaurant"]
    if category == "hotel":
        return ["hotel", "homestay", "resort", "hostel", "guesthouse"]
    if category == "attraction":
        return ["attraction", "entertainment"]
    return [category]


def _location_result(location: Location, *, source: str) -> dict:
    return {
        column.name: getattr(location, column.name)
        for column in location.__table__.columns
    } | {"result_source": source}


async def explore_dataset_locations(
    db: AsyncSession,
    *,
    destination: str,
    category: str | None,
    page: int,
    limit: int,
) -> dict:
    """Paginated local dataset exploration. This function never calls an external API."""
    filters = (
        Location.source_dataset_id.is_not(None),
        Location.status == "active",
        Location.province_name.in_(_province_query_names(destination)),
        Location.category.in_(_explore_categories(category)),
    )
    total = int(
        await db.scalar(select(func.count()).select_from(Location).where(*filters))
        or 0
    )
    confidence_order = case(
        (Location.data_confidence == "high", 0),
        (Location.data_confidence == "medium", 1),
        else_=2,
    )
    coordinate_order = case(
        (Location.coordinate_status == "exact", 0),
        (Location.coordinate_status == "approximate", 1),
        else_=2,
    )
    result = await db.execute(
        select(Location)
        .where(*filters)
        .order_by(confidence_order, coordinate_order, Location.name)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    locations = list(result.scalars().all())
    return {
        "items": [_location_result(location, source="dataset") for location in locations],
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": page * limit < total,
    }


def _rank_dataset_search(
    locations: list[Location],
    query: str,
    *,
    limit: int,
) -> list[Location]:
    query_key = normalize_vietnamese(query)
    tokens = [token for token in query_key.split() if len(token) > 1]
    ranked: list[tuple[float, Location]] = []
    for location in locations:
        name = normalize_vietnamese(location.name or "")
        address = normalize_vietnamese(location.address or "")
        tags = " ".join(
            normalize_vietnamese(str(tag))
            for tag in (location.tags or [])
        )
        haystack = f"{name} {address} {tags}"
        if query_key not in haystack and not all(token in haystack for token in tokens):
            continue
        score = 0.0
        if name == query_key:
            score += 120
        elif name.startswith(query_key):
            score += 80
        elif query_key in name:
            score += 60
        score += 8 * sum(token in name for token in tokens)
        score += 3 * sum(token in address for token in tokens)
        if location.data_confidence == "high":
            score += 15
        elif location.data_confidence == "medium":
            score += 8
        if location.coordinate_status in {"exact", "approximate"}:
            score += 5
        ranked.append((score, location))
    ranked.sort(key=lambda item: (-item[0], normalize_vietnamese(item[1].name)))
    return [location for _, location in ranked[:limit]]


async def search_locations_hybrid(
    db: AsyncSession,
    *,
    query: str,
    destination: str | None,
    category: str | None,
    limit: int,
    include_external: bool,
) -> list[dict]:
    """Search the imported dataset first, then merge external results on explicit search."""
    filters = [
        Location.source_dataset_id.is_not(None),
        Location.status == "active",
        Location.category.in_(_explore_categories(category)),
    ]
    if destination:
        filters.append(Location.province_name.in_(_province_query_names(destination)))
    result = await db.execute(select(Location).where(*filters).limit(2_000))
    external_reserve = min(10, max(limit // 3, 5)) if include_external else 0
    local_matches = _rank_dataset_search(
        list(result.scalars().all()),
        query,
        limit=max(limit - external_reserve, 1),
    )
    merged = [_location_result(location, source="dataset") for location in local_matches]

    if include_external:
        try:
            external_locations = await search_external_locations_by_name(
                db,
                query=query,
                destination=destination,
                limit=external_reserve,
            )
        except Exception as exc:
            print(f"[LocationService] external explicit search failed: {exc}")
            external_locations = []

        seen_ids = {str(item.get("id")) for item in merged}
        seen_keys = {
            _candidate_dict_key(item)
            for item in merged
        }
        allowed_categories = set(_explore_categories(category))
        for location in external_locations:
            mapped_category = _scheduler_category(location.category)
            if category and mapped_category != "other" and mapped_category not in {
                _scheduler_category(value) for value in allowed_categories
            }:
                continue
            item = _location_result(location, source="external")
            key = _candidate_dict_key(item)
            if str(item.get("id")) in seen_ids or key in seen_keys:
                continue
            merged.append(item)
            seen_ids.add(str(item.get("id")))
            seen_keys.add(key)
            if len(merged) >= limit:
                break
    return merged[:limit]


async def search_external_locations_by_name(
    db: AsyncSession,
    *,
    query: str,
    destination: str | None,
    limit: int,
) -> list[Location]:
    """Explicit user search via Nominatim; never used by the default explore feed."""
    full_query = ", ".join(
        part for part in (query.strip(), (destination or "").strip(), "Việt Nam") if part
    )
    async with httpx.AsyncClient(timeout=settings.EXTERNAL_HTTP_TIMEOUT_SECONDS) as client:
        response = await client.get(
            f"{_NOMINATIM_URL}/search",
            params={
                "q": full_query,
                "format": "json",
                "limit": max(1, min(limit, 20)),
                "addressdetails": 1,
                "accept-language": "vi",
                "countrycodes": "vn",
            },
            headers=_HEADERS,
        )
        response.raise_for_status()
        raw_results = response.json()

    locations: list[Location] = []
    for place in raw_results:
        try:
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
            locations.append(location)
        except (KeyError, TypeError, ValueError):
            continue
    return locations


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
    must_visit_location_ids: set[str] | None = None,
    interests: list[str] | None = None,
    limit_per_query: int = 8,
    allow_external_fallback: bool = True,
) -> list[dict]:
    """Build a DB-first grounded place pool, with OSM as a sparse-data fallback."""
    must_visit = [p.strip() for p in (must_visit or []) if p and p.strip()]
    must_visit_location_ids = must_visit_location_ids or set()
    interests = [i.strip().lower() for i in (interests or []) if i and i.strip()]

    database_candidates = await _discover_database_candidates(
        db,
        destination=destination,
        must_visit=must_visit,
        must_visit_location_ids=must_visit_location_ids,
        interests=interests,
    )
    database_candidates = _keep_best_must_visit_matches(database_candidates)
    if _candidate_pool_is_sufficient(database_candidates):
        return _assign_candidate_refs(_select_diverse_candidates(database_candidates, 80))
    if not allow_external_fallback:
        return _assign_candidate_refs(_select_diverse_candidates(database_candidates, 80))

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

    candidates = list(database_candidates)
    for loc in deduped.values():
        category = _scheduler_category(loc.category)
        must_match = _match_requested_place(loc.name, must_visit)
        if str(loc.id) in must_visit_location_ids:
            must_match = next(
                (name for name in must_visit if _match_requested_place(loc.name, [name])),
                loc.name,
            )
        must_visit_id_match = str(loc.id) in must_visit_location_ids
        score = _score_candidate(loc, must_match=must_match, interests=interests)
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
                "must_visit_id_match": must_visit_id_match,
                "opening_hours": getattr(loc, "opening_hours", None),
                "price": getattr(loc, "price", None),
                "typical_visit_minutes": getattr(loc, "typical_visit_minutes", None),
                "data_confidence": getattr(loc, "data_confidence", None),
                "coordinate_status": getattr(loc, "coordinate_status", None),
                "coordinate_accuracy_meters": getattr(loc, "coordinate_accuracy_meters", None),
                "constraints": getattr(loc, "constraints", None) or {},
                "dataset_version": getattr(loc, "dataset_version", None),
            }
        )

    deduped_candidates: dict[str, dict] = {}
    for candidate in candidates:
        key = str(candidate.get("location_id") or _candidate_dict_key(candidate))
        previous = deduped_candidates.get(key)
        if previous is None or float(candidate.get("score") or 0) > float(previous.get("score") or 0):
            deduped_candidates[key] = candidate
    resolved_candidates = _keep_best_must_visit_matches(list(deduped_candidates.values()))
    selected = _select_diverse_candidates(resolved_candidates, 80)
    return _assign_candidate_refs(selected)


async def _discover_database_candidates(
    db: AsyncSession,
    *,
    destination: str,
    must_visit: list[str],
    must_visit_location_ids: set[str],
    interests: list[str],
) -> list[dict]:
    province_names = province_search_names(destination)
    statement = (
        select(Location)
        .where(
            Location.province_name.in_(province_names),
            Location.status == "active",
            Location.category.in_(
                [
                    "attraction",
                    "entertainment",
                    "restaurant",
                    "cafe",
                    "hotel",
                    "homestay",
                    "resort",
                    "hostel",
                    "guesthouse",
                ]
            ),
        )
        .limit(1_500)
    )
    result = await db.execute(statement)
    locations = list(result.scalars().all())
    candidates: list[dict] = []
    for location in locations:
        constraints = location.constraints or {}
        if constraints.get("avoid_auto_schedule") is True:
            continue
        must_match = _match_requested_place(location.name, must_visit)
        if str(location.id) in must_visit_location_ids:
            must_match = next(
                (name for name in must_visit if _match_requested_place(location.name, [name])),
                location.name,
            )
        must_visit_id_match = str(location.id) in must_visit_location_ids
        score = _score_candidate(location, must_match=must_match, interests=interests)
        candidates.append(
            {
                "ref": "",
                "location_id": str(location.id),
                "name": location.name,
                "address": location.address,
                "lat": location.lat,
                "lng": location.lng,
                "category": _scheduler_category(location.category),
                "source_category": location.category,
                "photo_url": location.photo_url,
                "rating": location.rating,
                "score": score,
                "must_visit_match": must_match,
                "must_visit_id_match": must_visit_id_match,
                "opening_hours": location.opening_hours,
                "price": location.price,
                "typical_visit_minutes": location.typical_visit_minutes,
                "tags": location.tags or [],
                "suitable_for": location.suitable_for or [],
                "data_confidence": location.data_confidence,
                "coordinate_status": location.coordinate_status,
                "coordinate_accuracy_meters": location.coordinate_accuracy_meters,
                "constraints": constraints,
                "dataset_version": location.dataset_version,
                "province_name": location.province_name,
            }
        )
    return candidates


def _candidate_pool_is_sufficient(candidates: list[dict]) -> bool:
    categories = [candidate.get("category") for candidate in candidates]
    return (
        len(candidates) >= 18
        and categories.count("attraction") >= 6
        and sum(category in {"restaurant", "cafe"} for category in categories) >= 4
        and categories.count("hotel") >= 2
    )


def _scheduler_category(category: str | None) -> str:
    if category in {"hotel", "homestay", "resort", "hostel", "guesthouse"}:
        return "hotel"
    if category == "entertainment":
        return "attraction"
    return category or "other"


def _select_diverse_candidates(candidates: list[dict], limit: int) -> list[dict]:
    ordered = sorted(
        candidates,
        key=lambda item: (
            0 if item.get("must_visit_match") else 1,
            -float(item.get("score") or 0),
            normalize_vietnamese(str(item.get("name") or "")),
        ),
    )
    quotas = {"attraction": 35, "restaurant": 20, "cafe": 10, "hotel": 15}
    selected: list[dict] = []
    overflow: list[dict] = []
    counts: dict[str, int] = {}
    for candidate in ordered:
        category = str(candidate.get("category") or "other")
        if candidate.get("must_visit_match") or counts.get(category, 0) < quotas.get(category, 5):
            selected.append(candidate)
            counts[category] = counts.get(category, 0) + 1
        else:
            overflow.append(candidate)
        if len(selected) >= limit:
            return selected[:limit]
    selected.extend(overflow[: max(limit - len(selected), 0)])
    return selected[:limit]


def _keep_best_must_visit_matches(candidates: list[dict]) -> list[dict]:
    """Resolve one grounded candidate per user request to avoid scheduling aliases twice."""
    matches: dict[str, list[dict]] = {}
    for candidate in candidates:
        match = candidate.get("must_visit_match")
        if match:
            matches.setdefault(normalize_vietnamese(str(match)), []).append(candidate)

    for normalized_request, group in matches.items():
        if len(group) <= 1:
            continue
        winner = min(
            group,
            key=lambda candidate: (
                0 if candidate.get("must_visit_id_match") else 1,
                0
                if normalize_vietnamese(str(candidate.get("name") or "")) == normalized_request
                else 1,
                -float(candidate.get("score") or 0),
                -float(candidate.get("rating") or 0),
            ),
        )
        for candidate in group:
            if candidate is not winner:
                candidate["must_visit_match"] = None
                candidate["score"] = max(
                    float(candidate.get("score") or 0) - 100,
                    0,
                )
    return candidates


def _assign_candidate_refs(candidates: list[dict]) -> list[dict]:
    for index, candidate in enumerate(candidates, start=1):
        candidate["ref"] = f"p{index}"
    return candidates


def _candidate_dict_key(candidate: dict) -> str:
    name = normalize_vietnamese(str(candidate.get("name") or ""))
    try:
        return f"{name}:{round(float(candidate.get('lat')), 4)}:{round(float(candidate.get('lng')), 4)}"
    except (TypeError, ValueError):
        return name


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
    data = payload.model_dump()
    if data.get("google_place_id") and not str(data["google_place_id"]).strip():
        data["google_place_id"] = None

    if data.get("google_place_id"):
        existing = await db.execute(
            select(Location).where(Location.google_place_id == data["google_place_id"])
        )
        found = existing.scalar_one_or_none()
        if found is not None:
            return found, False

    if data.get("name"):
        stmt = select(Location).where(Location.name == data["name"])
        if data.get("lat") is not None and data.get("lng") is not None:
            stmt = stmt.where(
                Location.lat.between(data["lat"] - 0.001, data["lat"] + 0.001),
                Location.lng.between(data["lng"] - 0.001, data["lng"] + 0.001),
            )
        existing = await db.execute(stmt)
        found = existing.scalars().first()
        if found is not None:
            return found, False

    location = Location(**data)
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
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").replace("đ", "d")


def _candidate_key(location: Location) -> str:
    name = _strip_accents(location.name or "").strip()
    if location.lat is not None and location.lng is not None:
        return f"{name}:{round(location.lat, 4)}:{round(location.lng, 4)}"
    return name


def _match_requested_place(name: str, requested_places: list[str]) -> str | None:
    clean_name = " ".join(_strip_accents(name).split())
    name_tokens = set(clean_name.split())
    for place in requested_places:
        clean_place = " ".join(_strip_accents(place).split())
        if clean_place and (clean_place in clean_name or clean_name in clean_place):
            return place
        if not clean_place:
            continue
        place_tokens = set(clean_place.split())
        token_overlap = len(name_tokens & place_tokens) / max(len(name_tokens | place_tokens), 1)
        similarity = SequenceMatcher(None, clean_name, clean_place).ratio()
        shared_tokens = name_tokens & place_tokens
        alias_overlap = (
            len(shared_tokens) >= 3
            and len(shared_tokens) / max(min(len(name_tokens), len(place_tokens)), 1) >= 0.6
        )
        if (
            similarity >= 0.78
            or (similarity >= 0.68 and token_overlap >= 0.5)
            or alias_overlap
        ):
            return place
    return None


def _score_candidate(
    location: Location,
    *,
    must_match: str | None,
    interests: list[str] | None = None,
) -> float:
    score = 10.0
    category = _scheduler_category((location.category or "").lower())
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
    confidence = str(getattr(location, "data_confidence", "") or "").lower()
    if confidence == "high":
        score += 20
    elif confidence == "medium":
        score += 10
    if getattr(location, "opening_hours", None):
        score += 12
    if getattr(location, "price", None):
        score += 8
    coordinate_status = getattr(location, "coordinate_status", None)
    if coordinate_status == "approximate":
        score -= 3
    elif coordinate_status in {"suspicious", "missing"}:
        score -= 40
    constraints = getattr(location, "constraints", None) or {}
    if constraints.get("live_check_required"):
        score -= 5
    normalized_tags = {
        normalize_vietnamese(str(tag))
        for tag in (getattr(location, "tags", None) or [])
    }
    for interest in interests or []:
        normalized_interest = normalize_vietnamese(interest)
        if normalized_interest and any(
            normalized_interest in tag or tag in normalized_interest for tag in normalized_tags
        ):
            score += 15
    return score
