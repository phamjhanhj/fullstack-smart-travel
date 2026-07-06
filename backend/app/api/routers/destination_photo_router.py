"""Router — Destination Photo (lấy ảnh chính xác cho địa điểm du lịch)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_admin_user, get_current_user
from app.core.rate_limit import rate_limit
from app.core.response import envelope
from app.db.session import get_db
from app.models.user import User
from app.services import destination_photo_service

router = APIRouter(prefix="/places", tags=["Places"])


@router.get("/photo", dependencies=[Depends(rate_limit("place_photo", settings.RATE_LIMIT_PHOTO_PER_MINUTE))])
async def get_destination_photo(
    query: str = Query(min_length=1, description="Tên địa điểm cần tìm ảnh"),
    count: int = Query(default=3, ge=1, le=10, description="Số lượng ảnh cần lấy"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lấy ảnh cho một địa điểm du lịch.
    Hệ thống 3 tầng: Foursquare → Wikimedia → Unsplash fallback.
    Kết quả được cache trong DB 30 ngày.
    """
    result = await destination_photo_service.get_destination_photos(db, query, count)
    return envelope(data=result)


@router.get("/best-rated", dependencies=[Depends(rate_limit("place_best_rated", settings.RATE_LIMIT_PHOTO_PER_MINUTE))])
async def get_best_rated_places(
    query: str = Query(min_length=1, description="Tên địa điểm hoặc khu vực"),
    count: int = Query(default=5, ge=1, le=10),
    current_user: User = Depends(get_current_user),
):
    """Trả về danh sách địa điểm xếp theo rating Foursquare giảm dần."""
    from app.services.destination_photo_service import _search_foursquare_with_rating

    results = await _search_foursquare_with_rating(query, count)
    return envelope(data={"query": query, "places": results})


@router.get("/stats")
async def get_photo_service_stats(current_user: User = Depends(get_admin_user)):
    """Theo dõi số lần gọi Foursquare thành công/thất bại — phục vụ debug quota."""
    from app.services.destination_photo_service import get_foursquare_stats
    return envelope(data=get_foursquare_stats())
