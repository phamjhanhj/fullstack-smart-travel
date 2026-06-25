"""
Business logic - Module 7: AI Chat & Suggestions.
Goi Groq API thuc (model Llama 3) - ho tro ca non-streaming va SSE streaming.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from groq import AsyncGroq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.activity import Activity
from app.models.chat import AiSuggestion, ChatMessage
from app.models.trip import DayPlan, Trip

_groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)

_SYSTEM_PROMPT_TEMPLATE = """Ban la tro ly du lich AI thong minh, am hieu Viet Nam.
Thong tin chuyen di hien tai:
- Diem den: {destination}
- Thoi gian: {start_date} den {end_date}
- Ngan sach: {budget} VND cho {num_travelers} nguoi
- So thich: {preferences}

Hay tra loi ngan gon, cu the, uu tien goi y dia diem/hoat dong phu hop ngan sach va so thich tren.
Tra loi bang tieng Viet, dung markdown de format danh sach khi can."""


def _build_system_prompt(trip: Trip) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(
        destination=trip.destination,
        start_date=trip.start_date.isoformat(),
        end_date=trip.end_date.isoformat(),
        budget=trip.budget or "khong gioi han",
        num_travelers=trip.num_travelers,
        preferences=trip.preferences or "khong co yeu cau dac biet",
    )


async def _load_recent_history(db: AsyncSession, trip_id: uuid.UUID, limit: int = 10) -> list[dict[str, str]]:
    """Lay N tin nhan gan nhat de lam context hoi thoai cho Groq (khong phai full history)."""
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.trip_id == trip_id).order_by(ChatMessage.created_at.desc()).limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.message} for m in messages]


async def _save_message(db: AsyncSession, trip_id: uuid.UUID, role: str, message: str) -> ChatMessage:
    chat_msg = ChatMessage(trip_id=trip_id, role=role, message=message)
    db.add(chat_msg)
    await db.commit()
    await db.refresh(chat_msg)
    return chat_msg


def _try_extract_suggestion(user_message: str, ai_message: str) -> dict[str, Any] | None:
    """
    Heuristic don gian: neu user hoi ve goi y dia diem (chua "goi y", "quan", "dia diem"...)
    thi danh dau type=place de tao AiSuggestion. Co the nang cap bang function calling cua Groq sau.
    """
    keywords = ["goi y", "quan", "dia diem", "noi an", "cho choi", "khach san"]
    if any(k in user_message.lower() for k in keywords):
        return {"title": "Goi y tu AI", "raw_response": ai_message}
    return None


async def send_message_non_stream(
    db: AsyncSession, trip: Trip, user_message: str
) -> tuple[ChatMessage, AiSuggestion | None]:
    """POST /trips/{id}/chat voi stream=false - goi Groq, luu lai user msg + assistant msg."""
    await _save_message(db, trip.id, "user", user_message)

    history = await _load_recent_history(db, trip.id)
    completion = await _groq_client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "system", "content": _build_system_prompt(trip)}, *history],
    )
    ai_text = completion.choices[0].message.content or ""

    assistant_msg = await _save_message(db, trip.id, "assistant", ai_text)

    suggestion = None
    extracted = _try_extract_suggestion(user_message, ai_text)
    if extracted:
        suggestion = AiSuggestion(trip_id=trip.id, type="place", content_json=extracted, status="pending")
        db.add(suggestion)
        await db.commit()
        await db.refresh(suggestion)

    return assistant_msg, suggestion


async def send_message_stream(db: AsyncSession, trip: Trip, user_message: str) -> AsyncGenerator[str, None]:
    """
    POST /trips/{id}/chat voi stream=true - tra ve async generator cho SSE.
    Moi chunk yield ra dung format: data: {...}\\n\\n
    """
    await _save_message(db, trip.id, "user", user_message)
    history = await _load_recent_history(db, trip.id)

    full_text = ""
    stream = await _groq_client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "system", "content": _build_system_prompt(trip)}, *history],
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if not delta:
            continue
        full_text += delta
        payload = {"status_code": 200, "message": "OK", "data": {"delta": delta}}
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    assistant_msg = await _save_message(db, trip.id, "assistant", full_text)

    suggestion_id = None
    extracted = _try_extract_suggestion(user_message, full_text)
    if extracted:
        suggestion = AiSuggestion(trip_id=trip.id, type="place", content_json=extracted, status="pending")
        db.add(suggestion)
        await db.commit()
        await db.refresh(suggestion)
        suggestion_id = str(suggestion.id)

    done_payload = {
        "status_code": 200,
        "message": "OK",
        "data": {"done": True, "message_id": str(assistant_msg.id), "suggestion_id": suggestion_id},
    }
    yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"


async def get_chat_history(db: AsyncSession, trip_id: uuid.UUID, limit: int) -> list[ChatMessage]:
    """GET /trips/{id}/chat/history - sap xep tang dan theo thoi gian."""
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.trip_id == trip_id).order_by(ChatMessage.created_at.asc()).limit(limit)
    )
    return list(result.scalars().all())


async def list_suggestions(db: AsyncSession, trip_id: uuid.UUID, status: str | None) -> list[AiSuggestion]:
    """GET /trips/{id}/suggestions."""
    query = select(AiSuggestion).where(AiSuggestion.trip_id == trip_id)
    if status:
        query = query.where(AiSuggestion.status == status)

    result = await db.execute(query.order_by(AiSuggestion.created_at.desc()))
    return list(result.scalars().all())


async def get_suggestion_owned_or_404(db: AsyncSession, suggestion_id: uuid.UUID, user_id: uuid.UUID) -> AiSuggestion:
    from app.core.exceptions import NotFoundError

    result = await db.execute(
        select(AiSuggestion)
        .join(Trip, AiSuggestion.trip_id == Trip.id)
        .where(AiSuggestion.id == suggestion_id, Trip.user_id == user_id)
    )
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise NotFoundError("Khong tim thay goi y nay")
    return suggestion


async def update_suggestion_status(db: AsyncSession, suggestion: AiSuggestion, new_status: str) -> int:
    """
    PATCH /suggestions/{id}/status.
    Neu accepted va type=itinerary: tu dong tao activities vao day_plan tuong ung.
    Tra ve so luong activities da tao (activities_created).
    """
    suggestion.status = new_status
    activities_created = 0

    if new_status == "accepted" and suggestion.type == "itinerary":
        content = suggestion.content_json
        day_number = content.get("day_number")

        day_result = await db.execute(
            select(DayPlan).where(DayPlan.trip_id == suggestion.trip_id, DayPlan.day_number == day_number)
        )
        day_plan = day_result.scalar_one_or_none()

        if day_plan is None:
            raise AppError(f"Khong tim thay ngay {day_number} de ap dung goi y", status_code=400)

        existing_count_result = await db.execute(
            select(Activity).where(Activity.day_plan_id == day_plan.id)
        )
        next_order_index = len(list(existing_count_result.scalars().all()))

        for activity_data in content.get("activities", []):
            new_activity = Activity(
                day_plan_id=day_plan.id,
                title=activity_data.get("title", "Hoat dong"),
                type=activity_data.get("type", "other"),
                start_time=activity_data.get("start_time"),
                end_time=activity_data.get("end_time"),
                estimated_cost=activity_data.get("estimated_cost"),
                order_index=next_order_index,
            )
            db.add(new_activity)
            next_order_index += 1
            activities_created += 1

    await db.commit()
    return activities_created
