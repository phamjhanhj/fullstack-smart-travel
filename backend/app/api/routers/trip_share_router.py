"""Routers for trip sharing and invite acceptance."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_trip_owner_access
from app.core.response import envelope, envelope_created
from app.db.session import get_db
from app.models.trip import Trip
from app.models.user import User
from app.schemas.trip_share import (
    AcceptTripInviteResponse,
    CreateTripInviteRequest,
    TripInviteNotificationResponse,
    TripInviteResponse,
    TripParticipantResponse,
    TripSharesResponse,
    UpdateTripParticipantRequest,
)
from app.services import trip_share_service

trip_shares_router = APIRouter(prefix="/trips/{trip_id}/shares", tags=["Trip Sharing"])
trip_invites_router = APIRouter(prefix="/trip-invites", tags=["Trip Sharing"])


def _invite_response(invite, token: str | None = None, email_sent: bool | None = None) -> TripInviteResponse:
    data = TripInviteResponse.model_validate(invite)
    if token:
        data.token = token
        data.accept_url = f"/trip-invites/{token}"
    data.email_sent = email_sent
    return data


def _invite_notification_response(invite) -> TripInviteNotificationResponse:
    return TripInviteNotificationResponse.model_validate(invite)


@trip_shares_router.get("")
async def list_shares(
    trip: Trip = Depends(get_trip_owner_access),
    db: AsyncSession = Depends(get_db),
):
    participants, invites = await trip_share_service.list_share_state(db, trip.id)
    return envelope(
        data=TripSharesResponse(
            participants=[TripParticipantResponse.model_validate(item) for item in participants],
            invites=[_invite_response(item) for item in invites],
        )
    )


@trip_shares_router.post("/invites", status_code=201)
async def create_invite(
    payload: CreateTripInviteRequest,
    trip: Trip = Depends(get_trip_owner_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    invite, token, email_sent = await trip_share_service.create_invite(db, trip, current_user, payload)
    return envelope_created(data=_invite_response(invite, token, email_sent), message="Da tao loi moi chia se")


@trip_invites_router.get("/pending")
async def list_pending_invites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    invites = await trip_share_service.list_pending_email_invites_for_user(db, current_user)
    return envelope(data=[_invite_notification_response(item) for item in invites])


@trip_invites_router.post("/{invite_id}/accept-email")
async def accept_email_invite(
    invite_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    participant = await trip_share_service.accept_email_invite(db, invite_id, current_user)
    return envelope(
        data=AcceptTripInviteResponse(trip_id=participant.trip_id, role=participant.role),
        message="Da chap nhan loi moi chia se",
    )


@trip_invites_router.post("/{invite_id}/reject")
async def reject_invite(
    invite_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await trip_share_service.reject_email_invite(db, invite_id, current_user)
    return envelope(data=None, message="Da tu choi loi moi")


@trip_shares_router.patch("/participants/{participant_id}")
async def update_participant(
    participant_id: uuid.UUID,
    payload: UpdateTripParticipantRequest,
    trip: Trip = Depends(get_trip_owner_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    participant = await trip_share_service.update_participant_role(db, trip.id, participant_id, payload.role, current_user)
    return envelope(data=TripParticipantResponse.model_validate(participant), message="Da cap nhat quyen chia se")


@trip_shares_router.delete("/participants/{participant_id}")
async def revoke_participant(
    participant_id: uuid.UUID,
    trip: Trip = Depends(get_trip_owner_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await trip_share_service.revoke_participant(db, trip.id, participant_id, current_user)
    return envelope(data=None, message="Da thu hoi quyen truy cap")


@trip_invites_router.post("/{token}/accept")
async def accept_invite(
    token: str = Path(min_length=32, max_length=256),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    participant = await trip_share_service.accept_invite(db, token, current_user)
    return envelope(
        data=AcceptTripInviteResponse(trip_id=participant.trip_id, role=participant.role),
        message="Da tham gia chuyen di duoc chia se",
    )


@trip_invites_router.delete("/{invite_id}")
async def revoke_invite(
    invite_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await trip_share_service.revoke_invite(db, invite_id, current_user.id)
    return envelope(data=None, message="Da huy loi moi")
