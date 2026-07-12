"""Trip history/audit helpers."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.trip_history import TripHistoryEvent


TRIP_FIELD_LABELS: dict[str, str] = {
    "title": "Ten chuyen di",
    "destination": "Diem den",
    "start_date": "Ngay bat dau",
    "end_date": "Ngay ket thuc",
    "budget": "Ngan sach",
    "num_travelers": "So nguoi di",
    "preferences": "So thich",
    "status": "Trang thai",
    "cover_image_url": "Anh bia",
}

ACTIVITY_FIELD_LABELS: dict[str, str] = {
    "title": "Ten hoat dong",
    "description": "Mo ta",
    "type": "Phan loai",
    "location_id": "Dia diem",
    "start_time": "Gio bat dau",
    "end_time": "Gio ket thuc",
    "estimated_cost": "Chi phi du kien",
    "order_index": "Thu tu",
    "booking_url": "Link dat cho",
    "notes": "Ghi chu",
}

BUDGET_FIELD_LABELS: dict[str, str] = {
    "category": "Hang muc",
    "label": "Noi dung",
    "planned_amount": "Du kien chi",
    "actual_amount": "Thuc chi",
    "date": "Ngay giao dich",
}

PARTICIPANT_FIELD_LABELS: dict[str, str] = {
    "role": "Quyen chia se",
    "status": "Trang thai",
}


def serialize_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    return str(value)


def snapshot_fields(entity: Any, fields: list[str]) -> dict[str, Any]:
    return {field: serialize_value(getattr(entity, field, None)) for field in fields}


def diff_snapshots(
    before: dict[str, Any],
    after: dict[str, Any],
    labels: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    field_labels = labels or {}
    changes: list[dict[str, Any]] = []
    for field, before_value in before.items():
        after_value = after.get(field)
        if before_value == after_value:
            continue
        changes.append(
            {
                "field": field,
                "label": field_labels.get(field, field),
                "before": before_value,
                "after": after_value,
            }
        )
    return changes


async def record_history_event(
    db: AsyncSession,
    *,
    trip_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    entity_type: str,
    action: str,
    summary: str,
    entity_id: uuid.UUID | None = None,
    changes: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> TripHistoryEvent:
    event = TripHistoryEvent(
        trip_id=trip_id,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        summary=summary,
        changes=serialize_value(changes or []),
        event_metadata=serialize_value(metadata or {}),
    )
    db.add(event)
    return event


async def list_history_events(
    db: AsyncSession,
    trip_id: uuid.UUID,
    *,
    page: int,
    limit: int,
    entity_type: str | None = None,
    action: str | None = None,
) -> tuple[list[TripHistoryEvent], int]:
    query = select(TripHistoryEvent).where(TripHistoryEvent.trip_id == trip_id)
    count_query = select(func.count()).select_from(TripHistoryEvent).where(TripHistoryEvent.trip_id == trip_id)

    if entity_type:
        query = query.where(TripHistoryEvent.entity_type == entity_type)
        count_query = count_query.where(TripHistoryEvent.entity_type == entity_type)
    if action:
        query = query.where(TripHistoryEvent.action == action)
        count_query = count_query.where(TripHistoryEvent.action == action)

    total_result = await db.execute(count_query)
    total = int(total_result.scalar_one())

    result = await db.execute(
        query.options(selectinload(TripHistoryEvent.actor))
        .order_by(TripHistoryEvent.created_at.desc(), TripHistoryEvent.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return list(result.scalars().all()), total


def history_event_payload(event: TripHistoryEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "trip_id": event.trip_id,
        "actor": event.actor,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "action": event.action,
        "summary": event.summary,
        "changes": event.changes or [],
        "metadata": event.event_metadata or {},
        "created_at": event.created_at,
    }
