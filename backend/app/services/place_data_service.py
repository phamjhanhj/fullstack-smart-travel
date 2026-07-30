"""Validation, normalization and idempotent import for the local Vietnam place dataset."""
from __future__ import annotations

import json
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Location

PLACE_UUID_NAMESPACE = uuid.UUID("48bced78-197f-4d68-9a39-e90230c41a52")
VIETNAM_BOUNDS = (8.0, 24.0, 102.0, 110.8)

_CATEGORY_MAP = {
    "attraction": "attraction",
    "nature_park": "attraction",
    "cultural": "attraction",
    "ẩm thực": "restaurant",
    "ăn vặt": "restaurant",
    "cafe": "cafe",
    "món uống & giải trí": "cafe",
    "hotel": "hotel",
    "accommodation": "hotel",
    "lodging": "hotel",
    "homestay": "homestay",
    "homestay_resort": "homestay",
    "resort": "resort",
    "bungalow": "resort",
    "farmstay": "resort",
    "hostel": "hostel",
    "guesthouse": "guesthouse",
    "motel": "guesthouse",
    "giải trí": "entertainment",
}


@dataclass
class DataIssue:
    severity: str
    code: str
    file: str
    place_id: str | None = None
    message: str = ""


@dataclass
class DataQualityReport:
    files: int = 0
    place_files: int = 0
    transportation_files: int = 0
    places: int = 0
    accepted: int = 0
    needs_review: int = 0
    rejected: int = 0
    issues: list[DataIssue] = field(default_factory=list)
    categories: Counter = field(default_factory=Counter)
    schema_versions: Counter = field(default_factory=Counter)

    def as_dict(self) -> dict[str, Any]:
        return {
            "files": self.files,
            "place_files": self.place_files,
            "transportation_files": self.transportation_files,
            "places": self.places,
            "accepted": self.accepted,
            "needs_review": self.needs_review,
            "rejected": self.rejected,
            "categories": dict(self.categories),
            "schema_versions": dict(self.schema_versions),
            "issue_counts": dict(Counter(issue.code for issue in self.issues)),
            "issues": [issue.__dict__ for issue in self.issues],
        }


def normalize_category(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in _CATEGORY_MAP:
        return _CATEGORY_MAP[raw]
    if "ẩm thực" in raw or "ăn " in raw:
        return "restaurant"
    if "giải trí" in raw:
        return "entertainment"
    return "other"


def stable_location_id(dataset_id: str, place_id: str) -> uuid.UUID:
    return uuid.uuid5(PLACE_UUID_NAMESPACE, f"{dataset_id}:{place_id}")


def coordinate_quality(lat: Any, lng: Any) -> tuple[str, int | None, list[str]]:
    flags: list[str] = []
    if lat is None or lng is None:
        return "missing", None, ["missing_coordinate"]
    try:
        lat_value, lng_value = float(lat), float(lng)
    except (TypeError, ValueError):
        return "missing", None, ["invalid_coordinate_type"]
    if not (-90 <= lat_value <= 90 and -180 <= lng_value <= 180):
        return "suspicious", None, ["coordinate_out_of_range"]
    min_lat, max_lat, min_lng, max_lng = VIETNAM_BOUNDS
    if not (min_lat <= lat_value <= max_lat and min_lng <= lng_value <= max_lng):
        flags.append("outside_vietnam_bbox")
    if abs(lat_value - lng_value) < 1e-9:
        flags.append("lat_equals_lng")
    if flags:
        return "suspicious", 5_000, flags
    # Dataset coordinates are useful for clustering but their source accuracy is
    # not guaranteed. Treat them as approximate until reverse-geocoded.
    return "approximate", 500, []


def _parse_verified_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(str(value)[:10])
        return datetime.combine(parsed, time.min, tzinfo=timezone.utc)
    except ValueError:
        return None


def normalize_place(meta: dict[str, Any], place: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    flags: list[str] = []
    dataset_id = str(meta.get("dataset_id") or "").strip()
    place_id = str(place.get("id") or "").strip()
    name = str(place.get("name") or "").strip()
    address = str(place.get("address") or "").strip()
    if not dataset_id:
        flags.append("missing_dataset_id")
    if not place_id:
        flags.append("missing_place_id")
    if not name:
        flags.append("missing_name")
    if not address:
        flags.append("missing_address")
    if any(flag in flags for flag in ("missing_dataset_id", "missing_place_id", "missing_name")):
        return None, flags

    coordinate_status, accuracy, coordinate_flags = coordinate_quality(place.get("lat"), place.get("lng"))
    flags.extend(coordinate_flags)
    verification = place.get("verification") if isinstance(place.get("verification"), dict) else {}
    confidence = str(verification.get("confidence") or "unverified").lower()
    verification_status = str(verification.get("status") or "unverified").lower()
    constraints = place.get("constraints") if isinstance(place.get("constraints"), dict) else {}
    status = "active"
    if coordinate_status in {"missing", "suspicious"} or verification_status not in {"verified", "active"}:
        status = "needs_review"
    if constraints.get("avoid_auto_schedule") is True:
        status = "needs_review"

    raw_category = str(place.get("category") or "")
    row = {
        "id": stable_location_id(dataset_id, place_id),
        "name": name,
        "address": address or None,
        "lat": float(place["lat"]) if place.get("lat") is not None else None,
        "lng": float(place["lng"]) if place.get("lng") is not None else None,
        "category": normalize_category(raw_category),
        "google_place_id": f"dataset:{dataset_id}:{place_id}",
        "photo_url": place.get("photo_url"),
        "rating": place.get("rating"),
        "source_dataset_id": dataset_id,
        "source_place_id": place_id,
        "dataset_version": str(meta.get("schema_version") or "unknown"),
        "province_code": str(place.get("province_code") or meta.get("province_code") or "") or None,
        "province_name": str(place.get("province_name") or meta.get("province_name") or "") or None,
        "district": place.get("district"),
        "ward": place.get("ward"),
        "subcategory": place.get("subcategory"),
        "raw_category": raw_category or None,
        "description": place.get("description"),
        "tags": place.get("tags") if isinstance(place.get("tags"), list) else [],
        "suitable_for": place.get("suitable_for") if isinstance(place.get("suitable_for"), list) else [],
        "typical_visit_minutes": place.get("typical_visit_minutes"),
        "opening_hours": place.get("opening_hours") if isinstance(place.get("opening_hours"), dict) else None,
        "price": place.get("price") if isinstance(place.get("price"), dict) else None,
        "contact": place.get("contact") if isinstance(place.get("contact"), dict) else None,
        "booking": place.get("booking") if isinstance(place.get("booking"), dict) else None,
        "constraints": constraints,
        "verification": verification,
        "sources": place.get("sources") if isinstance(place.get("sources"), list) else [],
        "data_confidence": confidence,
        "coordinate_status": coordinate_status,
        "coordinate_accuracy_meters": accuracy,
        "status": status,
        "last_verified_at": _parse_verified_at(verification.get("last_verified_at")),
        "updated_at": datetime.now(timezone.utc),
    }
    return row, flags


def iter_dataset_files(data_dir: Path) -> Iterable[Path]:
    return sorted(path for path in data_dir.rglob("*.json") if path.is_file())


def scan_dataset(data_dir: Path, *, include_rows: bool = False) -> tuple[DataQualityReport, list[dict[str, Any]]]:
    report = DataQualityReport()
    rows: list[dict[str, Any]] = []
    scoped_ids: set[tuple[str, str]] = set()

    for path in iter_dataset_files(data_dir):
        report.files += 1
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            report.rejected += 1
            report.issues.append(DataIssue("error", "invalid_json", str(path), message=str(exc)))
            continue

        meta = document.get("meta") if isinstance(document.get("meta"), dict) else {}
        version = str(meta.get("schema_version") or "missing")
        report.schema_versions[version] += 1
        if version != "1.0":
            report.issues.append(
                DataIssue("warning", "unexpected_schema_version", str(path), message=version)
            )

        places = document.get("places")
        if not isinstance(places, list):
            if isinstance(document.get("transportation"), list):
                report.transportation_files += 1
                continue
            report.issues.append(DataIssue("error", "missing_places_array", str(path)))
            report.rejected += 1
            continue

        report.place_files += 1
        for place in places:
            report.places += 1
            if not isinstance(place, dict):
                report.rejected += 1
                report.issues.append(DataIssue("error", "invalid_place", str(path)))
                continue
            row, flags = normalize_place(meta, place)
            place_id = str(place.get("id") or "") or None
            if row is None:
                report.rejected += 1
            else:
                scoped_key = (row["source_dataset_id"], row["source_place_id"])
                if scoped_key in scoped_ids:
                    flags.append("duplicate_scoped_id")
                    row["status"] = "needs_review"
                scoped_ids.add(scoped_key)
                report.categories[row["category"]] += 1
                if row["status"] == "active":
                    report.accepted += 1
                else:
                    report.needs_review += 1
                if include_rows:
                    rows.append(row)
            for flag in flags:
                severity = "error" if row is None else "warning"
                report.issues.append(DataIssue(severity, flag, str(path), place_id))

    return report, rows


async def import_dataset(
    db: AsyncSession,
    data_dir: Path,
    *,
    dry_run: bool = False,
    batch_size: int = 500,
) -> DataQualityReport:
    report, scanned_rows = scan_dataset(data_dir, include_rows=True)
    rows_by_source: dict[tuple[str, str], dict[str, Any]] = {}
    for row in scanned_rows:
        key = (row["source_dataset_id"], row["source_place_id"])
        # Preserve the first occurrence and report later duplicates instead of
        # sending duplicate conflict keys in one PostgreSQL INSERT statement.
        rows_by_source.setdefault(key, row)
    rows = list(rows_by_source.values())
    if dry_run or not rows:
        return report

    update_columns = {
        key: getattr(insert(Location).excluded, key)
        for key in rows[0]
        if key not in {"id", "source_dataset_id", "source_place_id", "imported_at"}
    }
    for offset in range(0, len(rows), batch_size):
        batch = rows[offset:offset + batch_size]
        statement = insert(Location).values(batch)
        statement = statement.on_conflict_do_update(
            constraint="uq_locations_source_dataset_place",
            set_=update_columns,
        )
        await db.execute(statement)
    await db.commit()
    return report
