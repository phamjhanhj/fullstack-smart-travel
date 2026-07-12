"""Business logic for trip sharing and role-based access."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.trip import Trip
from app.models.trip_share import TripParticipant, TripShareInvite
from app.models.user import User
from app.schemas.trip_share import CreateTripInviteRequest
from app.services import trip_history_service

EDIT_ROLES = {"owner", "editor"}
PARTICIPANT_ROLES = {"viewer", "editor"}


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_invite_token() -> str:
    return secrets.token_urlsafe(32)


def attach_access(trip: Trip, role: str) -> Trip:
    trip._access_role = role  # type: ignore[attr-defined]
    trip._access_type = "owner" if role == "owner" else "shared"  # type: ignore[attr-defined]
    return trip


async def get_accessible_trip_or_404(db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID) -> Trip:
    result = await db.execute(select(Trip).where(Trip.id == trip_id).options(selectinload(Trip.user)))
    trip = result.scalar_one_or_none()
    if trip is None:
        raise NotFoundError("Khong tim thay chuyen di")

    if trip.user_id == user_id:
        return attach_access(trip, "owner")

    participant = await get_participant(db, trip_id, user_id)
    if participant is None:
        raise ForbiddenError("Ban khong co quyen truy cap chuyen di nay")

    return attach_access(trip, participant.role)


async def get_editable_trip_or_404(db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID) -> Trip:
    trip = await get_accessible_trip_or_404(db, trip_id, user_id)
    if getattr(trip, "_access_role", None) not in EDIT_ROLES:
        raise ForbiddenError("Ban khong co quyen chinh sua chuyen di nay")
    return trip


async def get_owned_trip_or_404(db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID) -> Trip:
    trip = await get_accessible_trip_or_404(db, trip_id, user_id)
    if getattr(trip, "_access_role", None) != "owner":
        raise ForbiddenError("Chi chu chuyen di moi co quyen thuc hien thao tac nay")
    return trip


async def get_participant(db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID) -> TripParticipant | None:
    result = await db.execute(
        select(TripParticipant).where(TripParticipant.trip_id == trip_id, TripParticipant.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def user_can_edit_trip(db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    result = await db.execute(select(Trip.user_id).where(Trip.id == trip_id))
    owner_id = result.scalar_one_or_none()
    if owner_id is None:
        return False
    if owner_id == user_id:
        return True
    participant = await get_participant(db, trip_id, user_id)
    return participant is not None and participant.role == "editor"


async def list_share_state(db: AsyncSession, trip_id: uuid.UUID) -> tuple[list[TripParticipant], list[TripShareInvite]]:
    participants_result = await db.execute(
        select(TripParticipant)
        .where(TripParticipant.trip_id == trip_id)
        .options(selectinload(TripParticipant.user), selectinload(TripParticipant.invited_by))
        .order_by(TripParticipant.created_at.desc())
    )
    invites_result = await db.execute(
        select(TripShareInvite)
        .where(TripShareInvite.trip_id == trip_id, TripShareInvite.status == "pending")
        .options(selectinload(TripShareInvite.invited_by), selectinload(TripShareInvite.accepted_by))
        .order_by(TripShareInvite.created_at.desc())
    )
    return list(participants_result.scalars().all()), list(invites_result.scalars().all())


async def create_invite(
    db: AsyncSession,
    trip: Trip,
    inviter: User,
    payload: CreateTripInviteRequest,
) -> tuple[TripShareInvite, str | None]:
    email = str(payload.email).lower() if payload.email else None
    invited_user: User | None = None
    if email and email == inviter.email.lower():
        raise AppError("Khong the moi chinh ban vao chuyen di")

    if email:
        user_result = await db.execute(select(User).where(User.email == email))
        invited_user = user_result.scalar_one_or_none()
        if invited_user and invited_user.id == trip.user_id:
            raise AppError("Khong the moi chu chuyen di")
        if invited_user and await get_participant(db, trip.id, invited_user.id):
            raise AppError("Nguoi dung nay da duoc chia se chuyen di")

        pending_result = await db.execute(
            select(TripShareInvite).where(
                TripShareInvite.trip_id == trip.id,
                TripShareInvite.email == email,
                TripShareInvite.status == "pending",
            )
        )
        pending_invite = pending_result.scalar_one_or_none()
        if pending_invite is not None:
            raise AppError("Da co loi moi dang cho cho email nay")

    token = new_invite_token()
    invite = TripShareInvite(
        trip_id=trip.id,
        email=email,
        token_hash=hash_invite_token(token),
        role=payload.role,
        status="pending",
        invited_by_user_id=inviter.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days),
    )

    db.add(invite)
    await db.flush()
    await trip_history_service.record_history_event(
        db,
        trip_id=trip.id,
        actor_user_id=inviter.id,
        entity_type="share_invite",
        entity_id=invite.id,
        action="created",
        summary=f"Da tao loi moi chia se quyen {invite.role}",
        metadata={"email": invite.email, "role": invite.role},
    )
    await db.commit()
    await db.refresh(invite)
    invite.invited_by = inviter
    return invite, token


async def list_pending_email_invites_for_user(db: AsyncSession, user: User) -> list[TripShareInvite]:
    result = await db.execute(
        select(TripShareInvite)
        .where(
            TripShareInvite.status == "pending",
            TripShareInvite.email.is_not(None),
            func.lower(TripShareInvite.email) == user.email.lower(),
        )
        .options(
            selectinload(TripShareInvite.trip).selectinload(Trip.user),
            selectinload(TripShareInvite.invited_by),
            selectinload(TripShareInvite.accepted_by),
        )
        .order_by(TripShareInvite.created_at.desc())
    )
    invites = list(result.scalars().all())
    now = datetime.now(timezone.utc)
    changed = False
    visible: list[TripShareInvite] = []
    for invite in invites:
        expires_at = invite.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            invite.status = "revoked"
            changed = True
            continue
        if invite.trip.user_id == user.id:
            invite.status = "revoked"
            changed = True
            continue
        if await get_participant(db, invite.trip_id, user.id):
            invite.status = "accepted"
            invite.accepted_by_user_id = user.id
            changed = True
            continue
        visible.append(invite)
    if changed:
        await db.commit()
    return visible


async def accept_email_invite(db: AsyncSession, invite_id: uuid.UUID, user: User) -> TripParticipant:
    invite = await get_pending_email_invite_for_user(db, invite_id, user)
    participant = TripParticipant(
        trip_id=invite.trip_id,
        user_id=user.id,
        role=invite.role,
        invited_by_user_id=invite.invited_by_user_id,
    )
    invite.status = "accepted"
    invite.accepted_by_user_id = user.id
    db.add(participant)
    await db.flush()
    await trip_history_service.record_history_event(
        db,
        trip_id=invite.trip_id,
        actor_user_id=user.id,
        entity_type="share_invite",
        entity_id=invite.id,
        action="accepted",
        summary=f"{user.full_name} da chap nhan loi moi chia se",
        metadata={"role": invite.role, "email": invite.email},
    )
    await db.commit()
    await db.refresh(participant)
    return participant


async def reject_email_invite(db: AsyncSession, invite_id: uuid.UUID, user: User) -> None:
    invite = await get_pending_email_invite_for_user(db, invite_id, user)
    invite.status = "rejected"
    invite.accepted_by_user_id = user.id
    await trip_history_service.record_history_event(
        db,
        trip_id=invite.trip_id,
        actor_user_id=user.id,
        entity_type="share_invite",
        entity_id=invite.id,
        action="rejected",
        summary=f"{user.full_name} da tu choi loi moi chia se",
        metadata={"role": invite.role, "email": invite.email},
    )
    await db.commit()


async def get_pending_email_invite_for_user(db: AsyncSession, invite_id: uuid.UUID, user: User) -> TripShareInvite:
    result = await db.execute(
        select(TripShareInvite)
        .where(
            TripShareInvite.id == invite_id,
            TripShareInvite.status == "pending",
            TripShareInvite.email.is_not(None),
            func.lower(TripShareInvite.email) == user.email.lower(),
        )
        .options(selectinload(TripShareInvite.trip))
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        raise NotFoundError("Khong tim thay loi moi")
    expires_at = invite.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        invite.status = "revoked"
        await db.commit()
        raise AppError("Loi moi da het han")
    if invite.trip.user_id == user.id:
        invite.status = "revoked"
        await db.commit()
        raise AppError("Chu chuyen di khong can chap nhan loi moi")
    if await get_participant(db, invite.trip_id, user.id):
        invite.status = "accepted"
        invite.accepted_by_user_id = user.id
        await db.commit()
        raise AppError("Ban da tham gia chuyen di nay")
    return invite


async def accept_invite(db: AsyncSession, token: str, user: User) -> TripParticipant:
    result = await db.execute(
        select(TripShareInvite)
        .where(TripShareInvite.token_hash == hash_invite_token(token))
        .options(selectinload(TripShareInvite.trip))
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        raise NotFoundError("Loi moi khong hop le")
    if invite.status != "pending":
        raise AppError("Loi moi khong con hieu luc")
    if invite.expires_at < datetime.now(timezone.utc):
        invite.status = "revoked"
        await db.commit()
        raise AppError("Loi moi da het han")
    if invite.email and invite.email.lower() != user.email.lower():
        raise ForbiddenError("Loi moi nay khong danh cho tai khoan cua ban")
    if invite.trip.user_id == user.id:
        raise AppError("Chu chuyen di khong can chap nhan loi moi")
    if await get_participant(db, invite.trip_id, user.id):
        raise AppError("Ban da tham gia chuyen di nay")

    participant = TripParticipant(
        trip_id=invite.trip_id,
        user_id=user.id,
        role=invite.role,
        invited_by_user_id=invite.invited_by_user_id,
    )
    invite.status = "accepted"
    invite.accepted_by_user_id = user.id
    db.add(participant)
    await db.flush()
    await trip_history_service.record_history_event(
        db,
        trip_id=invite.trip_id,
        actor_user_id=user.id,
        entity_type="share_invite",
        entity_id=invite.id,
        action="accepted",
        summary=f"{user.full_name} da tham gia chuyen di duoc chia se",
        metadata={"role": invite.role, "email": invite.email},
    )
    await db.commit()
    await db.refresh(participant)
    return participant


async def update_participant_role(
    db: AsyncSession,
    trip_id: uuid.UUID,
    participant_id: uuid.UUID,
    role: str,
    actor: User,
) -> TripParticipant:
    result = await db.execute(
        select(TripParticipant)
        .where(TripParticipant.id == participant_id, TripParticipant.trip_id == trip_id)
        .options(selectinload(TripParticipant.user), selectinload(TripParticipant.invited_by))
    )
    participant = result.scalar_one_or_none()
    if participant is None:
        raise NotFoundError("Khong tim thay nguoi duoc chia se")
    before_role = participant.role
    participant.role = role
    if before_role != role:
        await trip_history_service.record_history_event(
            db,
            trip_id=trip_id,
            actor_user_id=actor.id,
            entity_type="participant",
            entity_id=participant.id,
            action="updated",
            summary=f"Da doi quyen cua {participant.user.full_name} tu {before_role} sang {role}",
            changes=[
                {
                    "field": "role",
                    "label": trip_history_service.PARTICIPANT_FIELD_LABELS["role"],
                    "before": before_role,
                    "after": role,
                }
            ],
            metadata={"user_id": participant.user_id},
        )
    await db.commit()
    await db.refresh(participant)
    return participant


async def revoke_participant(db: AsyncSession, trip_id: uuid.UUID, participant_id: uuid.UUID, actor: User) -> None:
    result = await db.execute(
        select(TripParticipant)
        .where(TripParticipant.id == participant_id, TripParticipant.trip_id == trip_id)
        .options(selectinload(TripParticipant.user))
    )
    participant = result.scalar_one_or_none()
    if participant is None:
        raise NotFoundError("Khong tim thay nguoi duoc chia se")
    await trip_history_service.record_history_event(
        db,
        trip_id=trip_id,
        actor_user_id=actor.id,
        entity_type="participant",
        entity_id=participant.id,
        action="deleted",
        summary=f"Da thu hoi quyen truy cap cua {participant.user.full_name}",
        metadata={"user_id": participant.user_id, "role": participant.role},
    )
    await db.delete(participant)
    await db.commit()


async def revoke_invite(db: AsyncSession, invite_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    result = await db.execute(
        select(TripShareInvite)
        .join(Trip, TripShareInvite.trip_id == Trip.id)
        .where(TripShareInvite.id == invite_id, Trip.user_id == owner_id)
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        raise NotFoundError("Khong tim thay loi moi")
    invite.status = "revoked"
    await trip_history_service.record_history_event(
        db,
        trip_id=invite.trip_id,
        actor_user_id=owner_id,
        entity_type="share_invite",
        entity_id=invite.id,
        action="revoked",
        summary="Da huy loi moi chia se",
        metadata={"email": invite.email, "role": invite.role},
    )
    await db.commit()
