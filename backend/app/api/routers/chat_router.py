"""
Router - Module 7: AI Chat & Suggestions (4 endpoints).
POST /trips/{id}/chat tra ve JSON binh thuong khi stream=false,
hoac StreamingResponse (text/event-stream) khi stream=true.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_owned_trip
from app.core.response import envelope
from app.db.session import get_db
from app.models.trip import Trip
from app.models.user import User
from app.schemas.chat import (
    AiSuggestionResponse,
    ChatHistoryItem,
    ChatMessageResponse,
    SendMessageRequest,
    SuggestionStatus,
    UpdateSuggestionStatusRequest,
    UpdateSuggestionStatusResponse,
)
from app.services import ai_service

chat_router = APIRouter(prefix="/trips/{trip_id}/chat", tags=["AI Chat"])


@chat_router.post("")
async def send_message(
    payload: SendMessageRequest,
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    if payload.stream:
        return StreamingResponse(
            ai_service.send_message_stream(db, trip, payload.message),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    assistant_msg, suggestion = await ai_service.send_message_non_stream(db, trip, payload.message)
    data = ChatMessageResponse(
        message_id=assistant_msg.id,
        role=assistant_msg.role,
        message=assistant_msg.message,
        suggestion_id=suggestion.id if suggestion else None,
        created_at=assistant_msg.created_at,
    )
    return envelope(data=data)


@chat_router.get("/history")
async def get_chat_history(
    limit: int = Query(default=50, ge=1, le=200),
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    messages = await ai_service.get_chat_history(db, trip.id, limit)
    return envelope(data=[ChatHistoryItem.model_validate(m) for m in messages])


suggestions_trip_router = APIRouter(prefix="/trips/{trip_id}/suggestions", tags=["AI Suggestions"])


@suggestions_trip_router.get("")
async def list_suggestions(
    status: SuggestionStatus | None = Query(default=None),
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    suggestions = await ai_service.list_suggestions(db, trip.id, status)
    return envelope(data=[AiSuggestionResponse.model_validate(s) for s in suggestions])


suggestions_router = APIRouter(prefix="/suggestions", tags=["AI Suggestions"])


@suggestions_router.patch("/{suggestion_id}/status")
async def update_suggestion_status(
    suggestion_id: uuid.UUID,
    payload: UpdateSuggestionStatusRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    suggestion = await ai_service.get_suggestion_owned_or_404(db, suggestion_id, current_user.id)
    activities_created = await ai_service.update_suggestion_status(db, suggestion, payload.status)

    message = "Da ap dung goi y vao lich trinh" if payload.status == "accepted" else "Da bo qua goi y"
    data = UpdateSuggestionStatusResponse(
        suggestion_id=suggestion.id,
        status=payload.status,
        activities_created=activities_created,
    )
    return envelope(data=data, message=message)
