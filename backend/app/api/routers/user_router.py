"""Router - Module 2: Users (2 endpoints)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import envelope
from app.core.rate_limit import rate_limit
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.models.public_trip import PublicTripPublication
from app.schemas.user import ChangePasswordRequest, PublicUserProfileResponse, UpdateProfileRequest, UserProfileResponse
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
async def get_profile(current_user: User = Depends(get_current_user)):
    return envelope(data=UserProfileResponse.model_validate(current_user))


@router.get("/public-search", dependencies=[Depends(rate_limit("public_search", 30))])
async def search_public_users(
    q: str = Query(min_length=1, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    """Tìm kiếm người dùng công khai theo username hoặc full_name."""
    keyword = f"%{q.strip()}%"
    users = list(
        (
            await db.execute(
                select(User)
                .where(
                    User.is_public_profile.is_(True),
                    or_(
                        User.username.ilike(keyword),
                        User.full_name.ilike(keyword),
                    ),
                )
                .order_by(User.full_name)
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    results = []
    for u in users:
        trip_count = int(
            (
                await db.execute(
                    select(func.count(PublicTripPublication.id)).where(
                        PublicTripPublication.author_user_id == u.id,
                        PublicTripPublication.status == "published",
                        PublicTripPublication.visibility == "public",
                        PublicTripPublication.moderation_status == "approved",
                    )
                )
            ).scalar_one()
        )
        results.append(
            {
                "id": str(u.id),
                "username": u.username,
                "full_name": u.full_name,
                "avatar_url": u.avatar_url,
                "public_bio": u.public_bio,
                "accepts_tour_bookings": u.accepts_tour_bookings,
                "public_trips_count": trip_count,
            }
        )
    return envelope(data=results)


@router.get("/public/{username}", dependencies=[Depends(rate_limit("public_profile", 60))])
async def get_public_profile(username: str = Path(min_length=1, max_length=39), db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.username == username, User.is_public_profile.is_(True)))
    if user is None:
        raise NotFoundError("Trang cá nhân này đang ở chế độ riêng tư hoặc không tồn tại")
    publications = list((await db.execute(
        select(PublicTripPublication)
        .where(
            PublicTripPublication.author_user_id == user.id,
            PublicTripPublication.status == "published",
            PublicTripPublication.visibility == "public",
            PublicTripPublication.moderation_status == "approved",
        )
        .order_by(PublicTripPublication.published_at.desc())
        .limit(50)
    )).scalars().all())
    trips = [{
        "id": str(item.id), "slug": item.slug, "title": item.title,
        "summary": item.summary, "destination": item.destination,
        "cover_image_url": item.cover_image_url, "duration_days": item.duration_days,
        "save_count": item.save_count, "view_count": item.view_count,
        "published_at": item.published_at,
    } for item in publications]
    return envelope(data=PublicUserProfileResponse(
        id=user.id, username=user.username, full_name=user.full_name,
        avatar_url=user.avatar_url, public_bio=user.public_bio,
        public_phone=user.public_phone if user.accepts_tour_bookings else None,
        public_zalo_url=user.public_zalo_url if user.accepts_tour_bookings else None,
        accepts_tour_bookings=user.accepts_tour_bookings, public_trips=trips,
    ))

@router.patch("/me")
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated_user = await user_service.update_profile(db, current_user, payload)
    return envelope(
        data=UserProfileResponse.model_validate(updated_user),
        message="Cap nhat thanh cong",
    )


@router.post("/me/password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await user_service.change_password(db, current_user, payload)
    return envelope(data=None, message="Doi mat khau thanh cong")
