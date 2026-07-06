"""
Business logic — Destination Photo Service.
Hệ thống 3 tầng lấy ảnh địa điểm:
  1. Foursquare Places API (ảnh thật, user upload) — 1000 req/ngày free
  2. Wikimedia Commons API (ảnh landmark nổi tiếng) — miễn phí, không giới hạn
  3. Unsplash fallback (ảnh đẹp chung) — hardcoded backup
"""
from __future__ import annotations

import unicodedata
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.destination_photo import DestinationPhoto

_CACHE_TTL_DAYS = 30  # Cache hết hạn sau 30 ngày

_HEADERS = {"User-Agent": "SmartTravelPlannerBackend/1.0 (contact@smarttravelplanner.com)"}

_foursquare_call_count = {"success": 0, "failure": 0}

def get_foursquare_stats() -> dict:
    """Trả về số liệu gọi Foursquare từ lúc server khởi động."""
    return dict(_foursquare_call_count)

# Unsplash/Pexels fallback — ảnh đẹp chung cho các địa điểm phổ biến
_UNSPLASH_FALLBACK: dict[str, list[str]] = {
    "đà nẵng": [
        "https://images.pexels.com/photos/9310155/pexels-photo-9310155.jpeg?auto=compress&cs=tinysrgb&w=600",
        "https://images.pexels.com/photos/10098485/pexels-photo-10098485.jpeg?auto=compress&cs=tinysrgb&w=600",
        "https://images.pexels.com/photos/2403402/pexels-photo-2403402.jpeg?auto=compress&cs=tinysrgb&w=600"
    ],
    "hà nội": [
        "https://images.pexels.com/photos/18413665/pexels-photo-18413665.jpeg?auto=compress&cs=tinysrgb&w=600",
        "https://images.pexels.com/photos/10086820/pexels-photo-10086820.jpeg?auto=compress&cs=tinysrgb&w=600",
        "https://images.pexels.com/photos/18313364/pexels-photo-18313364.jpeg?auto=compress&cs=tinysrgb&w=600"
    ],
    "phú quốc": [
        "https://images.pexels.com/photos/1007631/pexels-photo-1007631.jpeg?auto=compress&cs=tinysrgb&w=600",
        "https://images.pexels.com/photos/1430677/pexels-photo-1430677.jpeg?auto=compress&cs=tinysrgb&w=600",
        "https://images.pexels.com/photos/2403251/pexels-photo-2403251.jpeg?auto=compress&cs=tinysrgb&w=600"
    ],
    "sapa": [
        "https://images.pexels.com/photos/2444429/pexels-photo-2444429.jpeg?auto=compress&cs=tinysrgb&w=600",
        "https://images.pexels.com/photos/15835691/pexels-photo-15835691.jpeg?auto=compress&cs=tinysrgb&w=600"
    ],
    "hà giang": [
        "https://images.pexels.com/photos/15316664/pexels-photo-15316664.jpeg?auto=compress&cs=tinysrgb&w=600",
        "https://images.pexels.com/photos/12318021/pexels-photo-12318021.jpeg?auto=compress&cs=tinysrgb&w=600"
    ],
    "hội an": [
        "https://images.pexels.com/photos/16843477/pexels-photo-16843477.jpeg?auto=compress&cs=tinysrgb&w=600",
        "https://images.pexels.com/photos/347141/pexels-photo-347141.jpeg?auto=compress&cs=tinysrgb&w=600"
    ],
    "đà lạt": [
        "https://images.pexels.com/photos/14812836/pexels-photo-14812836.jpeg?auto=compress&cs=tinysrgb&w=600",
        "https://images.pexels.com/photos/11181298/pexels-photo-11181298.jpeg?auto=compress&cs=tinysrgb&w=600"
    ],
    "tokyo": [
        "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?q=80&w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1503899036084-c55cdd92da26?q=80&w=600&auto=format&fit=crop"
    ],
    "bali": [
        "https://images.unsplash.com/photo-1537996194471-e657df975ab4?q=80&w=600&auto=format&fit=crop"
    ],
    "paris": [
        "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?q=80&w=600&auto=format&fit=crop"
    ],
    "london": [
        "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?q=80&w=600&auto=format&fit=crop"
    ],
    "nha trang": [
        "https://images.unsplash.com/photo-1559592443-7f87a79f6386?q=80&w=600&auto=format&fit=crop"
    ],
}

_DEFAULT_FALLBACK = "https://images.pexels.com/photos/1007631/pexels-photo-1007631.jpeg?auto=compress&cs=tinysrgb&w=600"


def _normalize_key(destination: str) -> str:
    """Chuan hoa ten dia diem: lowercase, strip, NFC unicode."""
    return unicodedata.normalize("NFC", destination.lower().strip())


# ---------------------------------------------------------------------------
# 1. DB Cache Layer
# ---------------------------------------------------------------------------

async def _get_cached(db: AsyncSession, key: str) -> list[str] | None:
    """Tra cache trong DB. Tra ve None neu khong co hoac het han."""
    result = await db.execute(
        select(DestinationPhoto).where(DestinationPhoto.destination_key == key)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    # Check TTL
    if row.fetched_at and row.fetched_at.tzinfo is None:
        fetched = row.fetched_at.replace(tzinfo=timezone.utc)
    else:
        fetched = row.fetched_at

    if datetime.now(timezone.utc) - fetched > timedelta(days=_CACHE_TTL_DAYS):
        return None  # Cache het han

    return row.photo_urls if row.photo_urls else None


async def _save_cache(db: AsyncSession, key: str, urls: list[str], source: str) -> None:
    """Luu hoac cap nhat cache trong DB."""
    result = await db.execute(
        select(DestinationPhoto).where(DestinationPhoto.destination_key == key)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.photo_urls = urls
        existing.source = source
        existing.fetched_at = datetime.now(timezone.utc)
    else:
        entry = DestinationPhoto(
            destination_key=key,
            photo_urls=urls,
            source=source,
        )
        db.add(entry)

    await db.commit()


# ---------------------------------------------------------------------------
# 2. Foursquare Places API
# ---------------------------------------------------------------------------

async def _search_foursquare(destination: str, count: int) -> list[str]:
    """Tim anh qua Foursquare Places API v3."""
    api_key = settings.FOURSQUARE_API_KEY
    if not api_key:
        return []

    try:
        async with httpx.AsyncClient(timeout=settings.EXTERNAL_HTTP_TIMEOUT_SECONDS) as client:
            # Step 1: Search for places matching the destination
            search_resp = await client.get(
                "https://api.foursquare.com/v3/places/search",
                params={
                    "query": destination,
                    "limit": min(count + 2, 10),  # fetch a few extras in case some lack photos
                },
                headers={
                    "Authorization": api_key,
                    "Accept": "application/json",
                    **_HEADERS,
                },
            )
            search_resp.raise_for_status()
            _foursquare_call_count["success"] += 1
            places = search_resp.json().get("results", [])

            if not places:
                return []

            photos: list[str] = []
            for place in places:
                if len(photos) >= count:
                    break

                fsq_id = place.get("fsq_id")
                if not fsq_id:
                    continue

                # Step 2: Get photos for each place
                try:
                    photo_resp = await client.get(
                        f"https://api.foursquare.com/v3/places/{fsq_id}/photos",
                        params={"limit": 3},
                        headers={
                            "Authorization": api_key,
                            "Accept": "application/json",
                            **_HEADERS,
                        },
                    )
                    photo_resp.raise_for_status()
                    _foursquare_call_count["success"] += 1
                    photo_list = photo_resp.json()

                    for p in photo_list:
                        if len(photos) >= count:
                            break
                        prefix = p.get("prefix", "")
                        suffix = p.get("suffix", "")
                        if prefix and suffix:
                            # Foursquare photo URL format: {prefix}{size}{suffix}
                            photos.append(f"{prefix}600x400{suffix}")
                except Exception:
                    _foursquare_call_count["failure"] += 1
                    continue  # Skip places whose photo endpoint fails

            return photos

    except Exception as exc:
        _foursquare_call_count["failure"] += 1
        print(f"[DestinationPhoto] Foursquare error for '{destination}': {exc}")
        return []


# ---------------------------------------------------------------------------
# 3. Wikimedia Commons API
# ---------------------------------------------------------------------------

async def _search_wikimedia(destination: str, count: int) -> list[str]:
    """Tim anh qua Wikimedia Commons / Wikipedia API."""
    try:
        async with httpx.AsyncClient(timeout=settings.EXTERNAL_HTTP_TIMEOUT_SECONDS) as client:
            # Try Wikipedia pageimages for the main article thumbnail
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "titles": destination,
                    "prop": "pageimages",
                    "format": "json",
                    "pithumbsize": 600,
                    "pilicense": "any",
                },
                headers=_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()

            photos: list[str] = []
            pages = data.get("query", {}).get("pages", {})
            for page_id, page in pages.items():
                if page_id == "-1":
                    continue
                thumb = page.get("thumbnail", {}).get("source")
                if thumb:
                    photos.append(thumb)

            if len(photos) >= count:
                return photos[:count]

            # Also try Vietnamese Wikipedia
            vi_resp = await client.get(
                "https://vi.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "titles": destination,
                    "prop": "pageimages",
                    "format": "json",
                    "pithumbsize": 600,
                    "pilicense": "any",
                },
                headers=_HEADERS,
            )
            vi_resp.raise_for_status()
            vi_data = vi_resp.json()

            vi_pages = vi_data.get("query", {}).get("pages", {})
            for page_id, page in vi_pages.items():
                if page_id == "-1":
                    continue
                thumb = page.get("thumbnail", {}).get("source")
                if thumb and thumb not in photos:
                    photos.append(thumb)

            return photos[:count]

    except Exception as exc:
        print(f"[DestinationPhoto] Wikimedia error for '{destination}': {exc}")
        return []


# ---------------------------------------------------------------------------
# 4. Unsplash Fallback
# ---------------------------------------------------------------------------

def _get_unsplash_fallback(destination: str, count: int) -> list[str]:
    """Lay anh fallback tu danh sach hardcoded."""
    key = _normalize_key(destination)

    # Try exact match first
    if key in _UNSPLASH_FALLBACK:
        return _UNSPLASH_FALLBACK[key][:count]

    # Try partial match
    for fk, urls in _UNSPLASH_FALLBACK.items():
        if fk in key or key in fk:
            return urls[:count]

    # Ultimate fallback
    return [_DEFAULT_FALLBACK]


def _build_photo_details(destination: str, urls: list[str], source: str) -> list[dict]:
    attribution_by_source = {
        "foursquare": "Foursquare Places",
        "wikimedia": "Wikimedia Commons / Wikipedia",
        "unsplash": "Pexels / Unsplash fallback",
        "cache": "Cached destination photo",
    }
    return [
        {
            "url": url,
            "thumbnail_url": url,
            "source": source,
            "attribution": attribution_by_source.get(source, source),
            "alt": f"Travel photo of {destination}",
            "width": 600,
            "height": 400,
            "quality_score": max(1.0 - (idx * 0.08), 0.5),
        }
        for idx, url in enumerate(urls)
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_destination_photos(
    db: AsyncSession,
    destination: str,
    count: int = 3,
) -> dict:
    """
    Lay danh sach anh cho mot dia diem.
    Tra ve dict { destination, photos: list[str], source: str }.
    """
    key = _normalize_key(destination)

    # 1. Check DB cache
    cached = await _get_cached(db, key)
    if cached and len(cached) > 0:
        cached_photos = cached[:count]
        return {
            "destination": destination,
            "photos": cached_photos,
            "photo_details": _build_photo_details(destination, cached_photos, "cache"),
            "source": "cache",
        }

    photos: list[str] = []
    source = "unsplash"

    # 2. Try Foursquare
    fsq_photos = await _search_foursquare(destination, count)
    if fsq_photos:
        photos.extend(fsq_photos)
        source = "foursquare"

    # 3. If not enough, try Wikimedia
    if len(photos) < count:
        wiki_photos = await _search_wikimedia(destination, count - len(photos))
        if wiki_photos:
            photos.extend(wiki_photos)
            if source == "unsplash":
                source = "wikimedia"

    # 4. If still not enough, use Unsplash fallback
    if len(photos) < count:
        fallback = _get_unsplash_fallback(destination, count - len(photos))
        photos.extend(fallback)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_photos: list[str] = []
    for url in photos:
        if url not in seen:
            seen.add(url)
            unique_photos.append(url)

    final_photos = unique_photos[:count]

    # 5. Save to DB cache
    await _save_cache(db, key, final_photos, source)

    return {
        "destination": destination,
        "photos": final_photos,
        "photo_details": _build_photo_details(destination, final_photos, source),
        "source": source,
    }


async def get_place_photo_by_coords(
    name: str,
    lat: float | None,
    lng: float | None,
    count: int = 1,
) -> list[str]:
    """
    Lấy ảnh cho MỘT địa điểm cụ thể (cafe, nhà hàng, nhà nghỉ) dựa vào tên
    + tọa độ thật từ OpenStreetMap — không qua DB cache vì số lượng địa
    điểm cụ thể quá lớn để cache hiệu quả như destination chung.
    """
    api_key = settings.FOURSQUARE_API_KEY
    if not api_key:
        return []

    try:
        async with httpx.AsyncClient(timeout=settings.EXTERNAL_HTTP_TIMEOUT_SECONDS) as client:
            params: dict = {"query": name, "limit": 1}
            if lat is not None and lng is not None:
                params["ll"] = f"{lat},{lng}"
                params["radius"] = 200  # mét — match đúng địa điểm gần tọa độ này

            search_resp = await client.get(
                "https://api.foursquare.com/v3/places/search",
                params=params,
                headers={"Authorization": api_key, "Accept": "application/json", **_HEADERS},
            )
            search_resp.raise_for_status()
            _foursquare_call_count["success"] += 1
            places = search_resp.json().get("results", [])
            if not places:
                return []

            fsq_id = places[0].get("fsq_id")
            if not fsq_id:
                return []

            photo_resp = await client.get(
                f"https://api.foursquare.com/v3/places/{fsq_id}/photos",
                params={"limit": count},
                headers={"Authorization": api_key, "Accept": "application/json", **_HEADERS},
            )
            photo_resp.raise_for_status()
            _foursquare_call_count["success"] += 1

            return [
                f"{p['prefix']}600x400{p['suffix']}"
                for p in photo_resp.json()
                if p.get("prefix") and p.get("suffix")
            ]

    except Exception as exc:
        _foursquare_call_count["failure"] += 1
        print(f"[PlacePhoto] Foursquare error for '{name}': {exc}")
        return []


async def _search_foursquare_with_rating(destination: str, count: int) -> list[dict]:
    """
    Giống _search_foursquare() nhưng trả về kèm rating + tên địa điểm,
    sắp xếp theo rating giảm dần — phục vụ tính năng "gợi ý tốt nhất".
    """
    api_key = settings.FOURSQUARE_API_KEY
    if not api_key:
        return []

    try:
        async with httpx.AsyncClient(timeout=settings.EXTERNAL_HTTP_TIMEOUT_SECONDS) as client:
            search_resp = await client.get(
                "https://api.foursquare.com/v3/places/search",
                params={"query": destination, "limit": min(count + 2, 10), "fields": "fsq_id,name,rating"},
                headers={"Authorization": api_key, "Accept": "application/json", **_HEADERS},
            )
            search_resp.raise_for_status()
            _foursquare_call_count["success"] += 1
            places = search_resp.json().get("results", [])

            places_with_rating = sorted(
                [p for p in places if p.get("rating") is not None],
                key=lambda p: p["rating"],
                reverse=True,
            )

            results: list[dict] = []
            for place in places_with_rating[:count]:
                fsq_id = place.get("fsq_id")
                try:
                    photo_resp = await client.get(
                        f"https://api.foursquare.com/v3/places/{fsq_id}/photos",
                        params={"limit": 1},
                        headers={"Authorization": api_key, "Accept": "application/json", **_HEADERS},
                    )
                    photo_resp.raise_for_status()
                    _foursquare_call_count["success"] += 1
                    photos = photo_resp.json()
                except Exception:
                    _foursquare_call_count["failure"] += 1
                    photos = []

                photo_url = (
                    f"{photos[0]['prefix']}600x400{photos[0]['suffix']}" if photos else None
                )

                results.append({
                    "name": place.get("name"),
                    "rating": place.get("rating"),
                    "photo_url": photo_url,
                })

            return results

    except Exception as exc:
        _foursquare_call_count["failure"] += 1
        print(f"[DestinationPhoto] Foursquare rating error for '{destination}': {exc}")
        return []
