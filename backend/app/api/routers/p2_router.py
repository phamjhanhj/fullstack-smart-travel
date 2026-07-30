from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_current_user, get_optional_current_user
from app.core.exceptions import AppError, NotFoundError
from app.core.response import envelope, envelope_created
from app.db.session import get_db
from app.models.p2_features import AuthorFollow, HiddenRecommendation, PublicTripComment, PublicTripRating
from app.models.user import User
from app.schemas.p2_features import CommentCreate, RatingCreate
from app.services import p2_service

router=APIRouter(tags=["Community P2"])

@router.get("/public-trips/{publication_id}/feedback")
async def get_feedback(publication_id:uuid.UUID, db:AsyncSession=Depends(get_db), current_user:User|None=Depends(get_optional_current_user)):
    publication=await p2_service.publication_or_404(db,publication_id); return envelope(data=await p2_service.feedback(db,publication,current_user.id if current_user else None))

@router.post("/public-trips/{publication_id}/comments",status_code=201)
async def add_comment(publication_id:uuid.UUID,payload:CommentCreate,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    publication=await p2_service.publication_or_404(db,publication_id)
    if not publication.allow_comments: raise AppError("Tác giả đã tắt bình luận")
    item=PublicTripComment(publication_id=publication.id,user_id=current_user.id,content=payload.content.strip(),is_verified_trip=await p2_service.has_verified_trip(db,current_user.id,publication)); db.add(item); publication.comment_count+=1; await db.commit(); await db.refresh(item)
    return envelope_created(data={"id":str(item.id),"content":item.content,"is_verified_trip":item.is_verified_trip,"created_at":item.created_at,"user":{"id":str(current_user.id),"username":current_user.username,"full_name":current_user.full_name,"avatar_url":current_user.avatar_url}})

@router.put("/public-trips/{publication_id}/rating")
async def rate(publication_id:uuid.UUID,payload:RatingCreate,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    publication=await p2_service.publication_or_404(db,publication_id); item=await db.scalar(select(PublicTripRating).where(PublicTripRating.publication_id==publication.id,PublicTripRating.user_id==current_user.id)); verified=await p2_service.has_verified_trip(db,current_user.id,publication)
    if item: item.rating=payload.rating; item.is_verified_trip=verified
    else: db.add(PublicTripRating(publication_id=publication.id,user_id=current_user.id,rating=payload.rating,is_verified_trip=verified))
    await db.commit(); return envelope(data={"rating":payload.rating,"is_verified_trip":verified})

@router.get("/authors/{author_id}/follow-status")
async def follow_status(author_id:uuid.UUID,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    following=await db.scalar(select(AuthorFollow.id).where(AuthorFollow.follower_user_id==current_user.id,AuthorFollow.author_user_id==author_id)); return envelope(data={"following":bool(following)})

@router.post("/authors/{author_id}/follow")
async def follow(author_id:uuid.UUID,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    await p2_service.follow_author(db,current_user.id,author_id); return envelope(data={"following":True})

@router.delete("/authors/{author_id}/follow")
async def unfollow(author_id:uuid.UUID,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    await db.execute(delete(AuthorFollow).where(AuthorFollow.follower_user_id==current_user.id,AuthorFollow.author_user_id==author_id)); await db.commit(); return envelope(data={"following":False})

@router.get("/recommendations/me")
async def recommend(limit:int=Query(12,ge=1,le=30),current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    return envelope(data=await p2_service.recommendations(db,current_user,limit))

@router.post("/recommendations/{publication_id}/hide")
async def hide_recommendation(publication_id:uuid.UUID,current_user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    db.add(HiddenRecommendation(user_id=current_user.id,publication_id=publication_id))
    try: await db.commit()
    except IntegrityError: await db.rollback()
    return envelope(data={"hidden":True})
