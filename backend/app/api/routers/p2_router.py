from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_admin_user, get_current_user, get_optional_current_user
from app.core.exceptions import AppError, NotFoundError
from app.core.response import envelope, envelope_created
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.p2_features import AuthorFollow, CommunityReport, HiddenRecommendation, PublicTripComment, PublicTripRating, TourBookingInquiry
from app.models.p1_features import UserNotification
from app.models.user import User
from app.models.public_trip import PublicTripPublication
from app.schemas.p2_features import BookingInquiryCreate, BookingInquiryStatusUpdate, CommentCreate, RatingCreate, ReportCreate, ReportStatusUpdate
from app.services import p2_service

router=APIRouter(tags=["Community P2"])

@router.get("/public-trips/{publication_id}/feedback", dependencies=[Depends(rate_limit("community_feedback", 120))])
async def get_feedback(publication_id:uuid.UUID, db:AsyncSession=Depends(get_db), current_user:User|None=Depends(get_optional_current_user)):
    publication=await p2_service.publication_or_404(db,publication_id); return envelope(data=await p2_service.feedback(db,publication,current_user.id if current_user else None))

@router.post("/public-trips/{publication_id}/comments", status_code=201, dependencies=[Depends(rate_limit("community_comment", 20))])
async def add_comment(publication_id:uuid.UUID,payload:CommentCreate,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    publication=await p2_service.publication_or_404(db,publication_id)
    if not publication.allow_comments: raise AppError("Tác giả đã tắt bình luận")
    item=PublicTripComment(publication_id=publication.id,user_id=current_user.id,content=payload.content.strip(),is_verified_trip=await p2_service.has_verified_trip(db,current_user.id,publication)); db.add(item); publication.comment_count+=1; await db.commit(); await db.refresh(item)
    user_rating = await db.scalar(select(PublicTripRating.rating).where(PublicTripRating.publication_id == publication.id, PublicTripRating.user_id == current_user.id))
    return envelope_created(data={"id":str(item.id),"content":item.content,"is_verified_trip":item.is_verified_trip,"rating":user_rating,"created_at":item.created_at,"user":{"id":str(current_user.id),"username":current_user.username,"full_name":current_user.full_name,"avatar_url":current_user.avatar_url}})

@router.put("/public-trips/{publication_id}/rating", dependencies=[Depends(rate_limit("community_rating", 30))])
async def rate(publication_id:uuid.UUID,payload:RatingCreate,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    publication=await p2_service.publication_or_404(db,publication_id); item=await db.scalar(select(PublicTripRating).where(PublicTripRating.publication_id==publication.id,PublicTripRating.user_id==current_user.id)); verified=await p2_service.has_verified_trip(db,current_user.id,publication)
    if item:
        raise AppError("Bạn đã đánh giá chuyến đi này rồi. Mỗi người dùng chỉ được đánh giá 1 lần duy nhất.")
    db.add(PublicTripRating(publication_id=publication.id,user_id=current_user.id,rating=payload.rating,is_verified_trip=verified))
    await db.commit(); return envelope(data={"rating":payload.rating,"is_verified_trip":verified}, message="Đã lưu đánh giá của bạn")

@router.get("/authors/{author_id}/follow-status")
async def follow_status(author_id:uuid.UUID,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    following=await db.scalar(select(AuthorFollow.id).where(AuthorFollow.follower_user_id==current_user.id,AuthorFollow.author_user_id==author_id)); return envelope(data={"following":bool(following)})

@router.post("/authors/{author_id}/follow", dependencies=[Depends(rate_limit("community_follow", 30))])
async def follow(author_id:uuid.UUID,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    await p2_service.follow_author(db,current_user.id,author_id); return envelope(data={"following":True})

@router.delete("/authors/{author_id}/follow", dependencies=[Depends(rate_limit("community_unfollow", 30))])
async def unfollow(author_id:uuid.UUID,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    await db.execute(delete(AuthorFollow).where(AuthorFollow.follower_user_id==current_user.id,AuthorFollow.author_user_id==author_id)); await db.commit(); return envelope(data={"following":False})

@router.get("/recommendations/me", dependencies=[Depends(rate_limit("community_recommendations", 60))])
async def recommend(limit:int=Query(12,ge=1,le=30),current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    return envelope(data=await p2_service.recommendations(db,current_user,limit))

@router.post("/recommendations/{publication_id}/hide", dependencies=[Depends(rate_limit("community_hide", 60))])
async def hide_recommendation(publication_id:uuid.UUID,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    db.add(HiddenRecommendation(user_id=current_user.id,publication_id=publication_id))
    try: await db.commit()
    except IntegrityError: await db.rollback()
    return envelope(data={"hidden":True})

@router.post("/public-trips/{publication_id}/report", status_code=201, dependencies=[Depends(rate_limit("community_report", 10))])
async def report_public_trip(publication_id: uuid.UUID, payload: ReportCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    publication = await p2_service.publication_or_404(db, publication_id)
    if publication.author_user_id == current_user.id:
        raise AppError("Ban khong the bao cao chuyen di cua chinh minh")
    db.add(CommunityReport(reporter_user_id=current_user.id, publication_id=publication.id, reason=payload.reason, details=payload.details))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError("Ban da bao cao chuyen di nay")
    report_count = await db.scalar(select(func.count()).select_from(CommunityReport).where(CommunityReport.publication_id == publication.id, CommunityReport.status == "open"))
    return envelope_created(data={"reported": True, "open_report_count": report_count or 1}, message="Da tiep nhan bao cao")


@router.post("/public-profiles/{username}/report", status_code=201, dependencies=[Depends(rate_limit("profile_report", 10))])
async def report_public_profile(username: str, payload: ReportCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    reported = await db.scalar(select(User).where(User.username == username, User.is_public_profile.is_(True)))
    if not reported:
        raise NotFoundError("Khong tim thay trang ca nhan cong khai")
    if reported.id == current_user.id:
        raise AppError("Ban khong the bao cao chinh minh")
    db.add(CommunityReport(reporter_user_id=current_user.id, reported_user_id=reported.id, reason=payload.reason, details=payload.details))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError("Ban da bao cao trang ca nhan nay")
    return envelope_created(data={"reported": True}, message="Da tiep nhan bao cao")


def _inquiry_payload(item: TourBookingInquiry, publication: PublicTripPublication) -> dict:
    return {
        "id": str(item.id), "publication_id": str(item.publication_id), "trip_title": publication.title,
        "requester_user_id": str(item.requester_user_id), "author_user_id": str(item.author_user_id),
        "contact_name": item.contact_name, "contact_phone": item.contact_phone,
        "travelers": item.travelers, "message": item.message, "status": item.status,
        "created_at": item.created_at, "updated_at": item.updated_at,
    }


@router.post("/public-trips/{publication_id}/booking-inquiries", status_code=201, dependencies=[Depends(rate_limit("booking_inquiry", 5))])
async def create_booking_inquiry(publication_id: uuid.UUID, payload: BookingInquiryCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    publication = await p2_service.publication_or_404(db, publication_id)
    author = await db.scalar(select(User).where(User.id == publication.author_user_id))
    if not author or not author.is_public_profile or not author.accepts_tour_bookings:
        raise AppError("Tac gia hien khong nhan yeu cau dat tour")
    if author.id == current_user.id:
        raise AppError("Ban khong the gui yeu cau cho chinh minh")
    item = TourBookingInquiry(publication_id=publication.id, requester_user_id=current_user.id, author_user_id=author.id, **payload.model_dump())
    db.add(item)
    db.add(UserNotification(
        user_id=author.id,
        type="booking_inquiry_received",
        title="Yeu cau dat tour moi",
        message=f"{payload.contact_name} da gui yeu cau cho {publication.title}",
        action_url="/profile?tab=bookings",
        payload_json={"inquiry_id": str(item.id), "publication_id": str(publication.id)},
        dedupe_key=f"booking-inquiry-received:{item.id}",
    ))
    await db.commit()
    await db.refresh(item)
    return envelope_created(data=_inquiry_payload(item, publication), message="Da gui yeu cau dat tour")


@router.get("/booking-inquiries/sent")
async def sent_booking_inquiries(limit: int = Query(100, ge=1, le=100), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(TourBookingInquiry, PublicTripPublication).join(PublicTripPublication, PublicTripPublication.id == TourBookingInquiry.publication_id).where(TourBookingInquiry.requester_user_id == current_user.id).order_by(TourBookingInquiry.created_at.desc()).limit(limit))).all()
    return envelope(data=[_inquiry_payload(item, publication) for item, publication in rows])


@router.get("/booking-inquiries/received")
async def received_booking_inquiries(limit: int = Query(100, ge=1, le=100), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(TourBookingInquiry, PublicTripPublication).join(PublicTripPublication, PublicTripPublication.id == TourBookingInquiry.publication_id).where(TourBookingInquiry.author_user_id == current_user.id).order_by(TourBookingInquiry.created_at.desc()).limit(limit))).all()
    return envelope(data=[_inquiry_payload(item, publication) for item, publication in rows])


@router.patch("/booking-inquiries/{inquiry_id}/status")
async def update_booking_inquiry_status(inquiry_id: uuid.UUID, payload: BookingInquiryStatusUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await db.scalar(select(TourBookingInquiry).where(TourBookingInquiry.id == inquiry_id, TourBookingInquiry.author_user_id == current_user.id))
    if not item:
        raise NotFoundError("Khong tim thay yeu cau dat tour")
    item.status = payload.status
    dedupe_key = f"booking-inquiry-status:{item.id}:{payload.status}"
    existing_notification = await db.scalar(select(UserNotification.id).where(UserNotification.dedupe_key == dedupe_key))
    if not existing_notification:
        db.add(UserNotification(
            user_id=item.requester_user_id,
            type="booking_inquiry_status",
            title="Yeu cau dat tour da cap nhat",
            message=f"Trang thai yeu cau cua ban: {payload.status}",
            action_url="/profile?tab=bookings",
            payload_json={"inquiry_id": str(item.id), "status": payload.status},
            dedupe_key=dedupe_key,
        ))
    await db.commit()
    publication = await db.scalar(select(PublicTripPublication).where(PublicTripPublication.id == item.publication_id))
    return envelope(data=_inquiry_payload(item, publication), message="Da cap nhat trang thai")
@router.get("/community-reports")
async def list_community_reports(status: str = Query("open", pattern="^(open|upheld|dismissed)$"), current_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    items = list((await db.execute(select(CommunityReport).where(CommunityReport.status == status).order_by(CommunityReport.created_at.asc()).limit(100))).scalars().all())
    return envelope(data=[{
        "id": str(item.id), "reporter_user_id": str(item.reporter_user_id),
        "publication_id": str(item.publication_id) if item.publication_id else None,
        "reported_user_id": str(item.reported_user_id) if item.reported_user_id else None,
        "reason": item.reason, "details": item.details, "status": item.status, "created_at": item.created_at,
    } for item in items])


@router.patch("/community-reports/{report_id}")
async def review_community_report(report_id: uuid.UUID, payload: ReportStatusUpdate, current_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    item = await db.scalar(select(CommunityReport).where(CommunityReport.id == report_id))
    if not item:
        raise NotFoundError("Khong tim thay bao cao")
    item.status = "upheld" if payload.decision == "uphold" else "dismissed"
    if item.publication_id and payload.decision == "uphold":
        publication = await db.scalar(select(PublicTripPublication).where(PublicTripPublication.id == item.publication_id))
        if publication:
            publication.moderation_status = "flagged"
    await db.commit()
    return envelope(data={"id": str(item.id), "status": item.status}, message="Da xu ly bao cao")
