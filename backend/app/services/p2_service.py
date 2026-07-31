from __future__ import annotations
import json, uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from app.core.exceptions import AppError, NotFoundError
from app.models.p1_features import UserNotification
from app.models.p2_features import AuthorFollow, HiddenRecommendation, PublicTripComment, PublicTripRating
from app.models.public_trip import PublicTripImport, PublicTripPublication, PublicTripSave
from app.models.trip import Trip
from app.models.user import User
from app.services import public_trip_service

async def publication_or_404(db: AsyncSession, publication_id: uuid.UUID) -> PublicTripPublication:
    item = await db.scalar(select(PublicTripPublication).where(PublicTripPublication.id == publication_id, PublicTripPublication.status == "published"))
    if not item: raise NotFoundError("Không tìm thấy lịch trình công khai")
    return item

async def has_verified_trip(db: AsyncSession, user_id: uuid.UUID, publication: PublicTripPublication) -> bool:
    own = await db.scalar(select(Trip.id).where(Trip.user_id == user_id, Trip.status == "completed", func.lower(Trip.destination) == publication.destination.lower()).limit(1))
    if own: return True
    imported = await db.scalar(select(PublicTripImport.id).join(Trip, Trip.id == PublicTripImport.target_trip_id).where(PublicTripImport.user_id == user_id, PublicTripImport.publication_id == publication.id, Trip.status == "completed").limit(1))
    return bool(imported)

async def sync_publication_rating(db: AsyncSession, publication_id: uuid.UUID) -> float | None:
    pub = await db.get(PublicTripPublication, publication_id)
    if not pub:
        return None

    author_rating_item = await db.scalar(
        select(PublicTripRating).where(
            PublicTripRating.publication_id == publication_id,
            PublicTripRating.user_id == pub.author_user_id
        )
    )
    if not author_rating_item:
        initial_val = pub.overall_rating or pub.itinerary_rating or 5
        author_rating = int(round(float(initial_val)))
        db.add(PublicTripRating(
            publication_id=publication_id,
            user_id=pub.author_user_id,
            rating=author_rating,
            is_verified_trip=True
        ))
        await db.flush()

    avg_val = await db.scalar(
        select(func.avg(PublicTripRating.rating)).where(PublicTripRating.publication_id == publication_id)
    )

    if avg_val is not None:
        new_overall = round(float(avg_val), 1)
        pub.overall_rating = new_overall
        await db.commit()
        return new_overall
    return None

async def feedback(db: AsyncSession, publication: PublicTripPublication, user_id: uuid.UUID | None) -> dict:
    await sync_publication_rating(db, publication.id)

    rows = await db.execute(
        select(PublicTripComment, User, PublicTripRating.rating)
        .join(User, User.id == PublicTripComment.user_id)
        .outerjoin(PublicTripRating, (PublicTripRating.publication_id == publication.id) & (PublicTripRating.user_id == PublicTripComment.user_id))
        .where(PublicTripComment.publication_id == publication.id)
        .order_by(PublicTripComment.created_at.desc())
        .limit(100)
    )
    comments = [
        {
            "id": c.id,
            "content": c.content,
            "is_verified_trip": c.is_verified_trip,
            "rating": rating,
            "created_at": c.created_at,
            "user": {
                "id": str(u.id),
                "username": u.username,
                "full_name": u.full_name,
                "avatar_url": u.avatar_url
            }
        }
        for c, u, rating in rows.all()
    ]
    avg, count = (await db.execute(select(func.avg(PublicTripRating.rating), func.count(PublicTripRating.id)).where(PublicTripRating.publication_id == publication.id))).one()
    mine = await db.scalar(select(PublicTripRating.rating).where(PublicTripRating.publication_id == publication.id, PublicTripRating.user_id == user_id)) if user_id else None
    return {"comments": comments, "rating_average": round(float(avg), 1) if avg is not None else None, "rating_count": count, "my_rating": mine}

async def follow_author(db: AsyncSession, follower_id: uuid.UUID, author_id: uuid.UUID) -> None:
    if follower_id == author_id: raise AppError("Bạn không thể theo dõi chính mình")
    db.add(AuthorFollow(follower_user_id=follower_id, author_user_id=author_id))
    try: await db.commit()
    except IntegrityError: await db.rollback()

async def notify_followers(db: AsyncSession, publication: PublicTripPublication) -> None:
    follower_ids = list((await db.execute(select(AuthorFollow.follower_user_id).where(AuthorFollow.author_user_id == publication.author_user_id))).scalars().all())
    for user_id in follower_ids:
        exists = await db.scalar(select(UserNotification.id).where(UserNotification.user_id == user_id, UserNotification.dedupe_key == f"author-publication:{publication.id}"))
        if not exists: db.add(UserNotification(user_id=user_id, type="author_publication", title="Tác giả bạn theo dõi vừa đăng bài", message=publication.title, action_url=f"/community/{publication.slug}", payload_json={"publication_id":str(publication.id)}, dedupe_key=f"author-publication:{publication.id}"))
    await db.commit()

async def recommendations(db: AsyncSession, user: User, limit: int = 12) -> list[dict]:
    hidden = select(HiddenRecommendation.publication_id).where(HiddenRecommendation.user_id == user.id)
    publications = list((
        await db.execute(
            select(PublicTripPublication)
            .where(
                PublicTripPublication.status == "published",
                PublicTripPublication.id.not_in(hidden),
            )
            .options(selectinload(PublicTripPublication.author))
            .order_by(PublicTripPublication.published_at.desc())
            .limit(80)
        )
    ).scalars().all())
    followed = set((await db.execute(select(AuthorFollow.author_user_id).where(AuthorFollow.follower_user_id == user.id))).scalars().all())
    saved_destinations = set((await db.execute(select(func.lower(PublicTripPublication.destination)).join(PublicTripSave, PublicTripSave.publication_id == PublicTripPublication.id).where(PublicTripSave.user_id == user.id))).scalars().all())
    preference_text = json.dumps(user.preferences_json or {}, ensure_ascii=False).lower()
    scored=[]
    for pub in publications:
        score=10; reasons=[]
        if pub.author_user_id in followed: score+=35; reasons.append("Từ tác giả bạn đang theo dõi")
        if pub.destination.lower() in saved_destinations: score+=30; reasons.append("Tương tự điểm đến bạn đã lưu")
        matches=[tag for tag in (pub.tags or []) if str(tag).lower() in preference_text]
        if matches: score+=min(25,len(matches)*8); reasons.append(f"Phù hợp sở thích: {', '.join(matches[:3])}")
        if pub.overall_rating and float(pub.overall_rating)>=4: score+=10; reasons.append("Được cộng đồng đánh giá tốt")
        scored.append({"publication": public_trip_service.publication_payload(pub), "reason": reasons[0] if reasons else "Lịch trình mới phù hợp để khám phá", "score":score})
    return sorted(scored,key=lambda item:item["score"],reverse=True)[:limit]
