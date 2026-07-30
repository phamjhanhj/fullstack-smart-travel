"""Lightweight destination topology inference for itinerary scheduling."""
from __future__ import annotations

import math
import unicodedata


_MOUNTAIN_DESTINATIONS = {
    "cao bang",
    "ha giang",
    "lao cai",
    "yen bai",
    "lai chau",
    "dien bien",
    "son la",
    "hoa binh",
    "bac kan",
    "lang son",
}

_ISLAND_DESTINATIONS = {"phu quoc", "con dao", "cat ba", "ly son", "co to"}
_COASTAL_DESTINATIONS = {
    "da nang",
    "nha trang",
    "phan thiet",
    "quy nhon",
    "vung tau",
}


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").replace("đ", "d").strip()


def _haversine_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    radius = 6371.0
    lat1, lng1 = map(math.radians, first)
    lat2, lng2 = map(math.radians, second)
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def build_destination_profile(destination: str, candidates: list[dict]) -> dict:
    normalized = _normalize(destination)
    topology = "compact_urban"
    if any(name in normalized or normalized in name for name in _MOUNTAIN_DESTINATIONS):
        topology = "mountain_corridor"
    elif any(name in normalized or normalized in name for name in _ISLAND_DESTINATIONS):
        topology = "island_land_route"
    elif any(name in normalized or normalized in name for name in _COASTAL_DESTINATIONS):
        topology = "linear_coastal"

    coordinates: list[tuple[float, float]] = []
    for candidate in candidates:
        try:
            coordinates.append((float(candidate["lat"]), float(candidate["lng"])))
        except (KeyError, TypeError, ValueError):
            continue

    max_span_km = 0.0
    if len(coordinates) >= 2:
        sample = coordinates[:120]
        for index, first in enumerate(sample):
            for second in sample[index + 1 :]:
                max_span_km = max(max_span_km, _haversine_km(first, second))

    if topology == "compact_urban" and max_span_km >= 45:
        topology = "multi_center_rural"

    return {
        "topology": topology,
        "max_span_km": round(max_span_km, 1),
        "supports_multi_lodging": topology in {"mountain_corridor", "multi_center_rural"},
        "route_strategy": "corridor" if topology == "mountain_corridor" else "cluster",
    }
