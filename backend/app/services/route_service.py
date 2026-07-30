"""Route duration estimation with optional OSRM and deterministic fallback."""
from __future__ import annotations

from dataclasses import dataclass
import math

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class RouteEstimate:
    distance_meters: int
    duration_minutes: int
    provider: str
    approximate: bool


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _fallback_estimate(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
    *,
    mode: str,
    uncertain: bool,
) -> RouteEstimate:
    straight = haversine_meters(lat1, lng1, lat2, lng2)
    road_factor = 1.18 if mode == "walking" else 1.35
    distance = straight * road_factor
    speed_kmh = {
        "walking": 4.5,
        "motorbike": 25.0,
        "car": 28.0,
        "taxi": 28.0,
        "public_transport": 18.0,
        "mixed": 24.0,
    }.get(mode, 24.0)
    minutes = max(5, math.ceil((distance / 1000) / speed_kmh * 60))
    minutes += 15 if uncertain else 8
    return RouteEstimate(round(distance), minutes, "haversine", True)


async def estimate_route(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
    *,
    mode: str = "mixed",
    uncertain: bool = False,
    offline_only: bool = False,
) -> RouteEstimate:
    if not offline_only and settings.ROUTING_PROVIDER.lower() == "osrm" and mode != "walking":
        profile = "driving"
        url = (
            f"{settings.OSRM_BASE_URL.rstrip('/')}/route/v1/{profile}/"
            f"{lng1},{lat1};{lng2},{lat2}"
        )
        try:
            async with httpx.AsyncClient(timeout=settings.EXTERNAL_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(url, params={"overview": "false", "steps": "false"})
                response.raise_for_status()
                routes = response.json().get("routes") or []
                if routes:
                    route = routes[0]
                    duration = max(1, math.ceil(float(route["duration"]) / 60))
                    if uncertain:
                        duration = math.ceil(duration * 1.2) + 5
                    return RouteEstimate(
                        distance_meters=round(float(route["distance"])),
                        duration_minutes=duration,
                        provider="osrm",
                        approximate=uncertain,
                    )
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            pass
    return _fallback_estimate(
        lat1,
        lng1,
        lat2,
        lng2,
        mode=mode,
        uncertain=uncertain,
    )
