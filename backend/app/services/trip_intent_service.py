"""Normalize free-form itinerary notes into deterministic planning constraints."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.schemas.day_plan import GenerateDaysRequest


@dataclass(frozen=True)
class ResolvedTripIntent:
    required_names: list[str]
    required_location_ids: set[str]
    unresolved_notes: list[str]
    accept_long_daily_travel: bool
    early_start_allowed: bool
    night_driving_allowed: bool


_REQUIRED_PATTERNS = (
    r"nhat dinh\s+(?:phai\s+)?(?:di\s+den|di|den|ghe|tham quan)\s+(.+)",
    r"bat buoc\s+(?:phai\s+)?(?:(?:di\s+den|di|den|ghe|tham quan)\s+)?(.+)",
    r"(?:toi\s+)?muon\s+(?:di\s+den|di|den|ghe|tham quan)\s+(.+)",
)

_TRAILING_PREFERENCE_MARKERS = (
    " ưu tiên ",
    " uu tien ",
    " có thể ",
    " co the ",
    " nhưng ",
    " nhung ",
    " và muốn ",
    " va muon ",
)

_PLACE_ACTION_PREFIX = re.compile(
    r"^(?:(?:toi|minh|chung toi|chung minh)\s+)?"
    r"(?:(?:nhat dinh|bat buoc)\s+(?:phai\s+)?|(?:muon|can|uu tien)\s+)?"
    r"(?:(?:di\s+den|di|den|ghe|ghe\s+tham|tham|tham\s+quan|"
    r"kham\s+pha|chinh\s+phuc|leo|dao\s+quanh|vieng|check[\s-]*in|"
    r"tam\s+bien|an|thuong\s+thuc)\s+)+",
    flags=re.IGNORECASE,
)

_TRAVEL_SUFFIX = re.compile(
    r"\s+(?:bang|voi)\s+(?:cap\s+treo|xe\s+may|o\s+to|taxi|xe\s+buyt|di\s+bo).*$",
    flags=re.IGNORECASE,
)

_PREFERENCE_QUALIFIER_SUFFIX = re.compile(
    r"\s+(?:thom\s+ngon|rat\s+ngon|ngon|noi\s+tieng|dac\s+san|hap\s+dan)$",
    flags=re.IGNORECASE,
)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").replace("đ", "d")


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip(" .,:;-")
        key = _normalize(clean)
        if len(clean) >= 2 and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def extract_required_places_from_notes(notes: str | None) -> list[str]:
    """Extract explicit place requests; ambiguous prose remains only as a soft note."""
    if not notes:
        return []

    places: list[str] = []
    for sentence in re.split(r"[\n;.!?]+", notes):
        text = sentence.strip()
        if not text:
            continue
        normalized = _normalize(text)
        for pattern in _REQUIRED_PATTERNS:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if not match:
                continue
            extracted = match.group(1).strip()
            for marker in _TRAILING_PREFERENCE_MARKERS:
                marker_index = extracted.find(marker)
                if marker_index >= 0:
                    extracted = extracted[:marker_index].strip()
            if extracted:
                places.append(extracted)
            break
    return _dedupe(places)


def extract_place_requests_from_preferences(preferences: str | None) -> list[str]:
    """Extract clauses that become required only after matching a Data place."""
    if not preferences:
        return []

    places: list[str] = []
    for clause in re.split(r"[\n,;.!?]+", preferences):
        normalized = " ".join(_normalize(clause).split()).strip()
        if not normalized:
            continue
        normalized = _PLACE_ACTION_PREFIX.sub("", normalized).strip()
        normalized = _TRAVEL_SUFFIX.sub("", normalized).strip()
        normalized = _PREFERENCE_QUALIFIER_SUFFIX.sub("", normalized).strip()
        normalized = re.sub(
            r"^(?:va|roi|sau do|ket hop|dong thoi)\s+",
            "",
            normalized,
        ).strip()
        if normalized:
            places.append(normalized)
    return _dedupe(places)


def resolve_trip_intent(payload: GenerateDaysRequest) -> ResolvedTripIntent:
    required_names = list(payload.must_visit)
    required_location_ids: set[str] = set()

    for item in payload.must_visit_items:
        if item.priority != "required":
            continue
        required_names.append(item.name)
        if item.location_id:
            required_location_ids.add(str(item.location_id))

    required_names.extend(extract_required_places_from_notes(payload.user_notes))
    normalized_notes = _normalize(payload.user_notes or "")
    inferred_long_travel = any(
        phrase in normalized_notes
        for phrase in (
            "co the di chuyen nhieu",
            "chap nhan di xa",
            "di nhieu trong ngay",
            "lich day",
        )
    )
    inferred_early_start = any(
        phrase in normalized_notes
        for phrase in ("co the di som", "xuat phat som", "day som")
    )
    inferred_night_driving = any(
        phrase in normalized_notes
        for phrase in ("chap nhan lai xe ban dem", "co the di dem", "di chuyen ban dem")
    ) and not any(
        phrase in normalized_notes
        for phrase in ("khong lai xe ban dem", "khong di dem", "tranh di dem")
    )

    return ResolvedTripIntent(
        required_names=_dedupe(required_names)[:20],
        required_location_ids=required_location_ids,
        unresolved_notes=[],
        accept_long_daily_travel=payload.accept_long_daily_travel or inferred_long_travel,
        early_start_allowed=payload.early_start_allowed or inferred_early_start,
        night_driving_allowed=payload.night_driving_allowed or inferred_night_driving,
    )
