from __future__ import annotations

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_trip_edit_access, get_trip_read_access
from app.core.exceptions import AppError, NotFoundError
from app.core.response import envelope, envelope_created
from app.db.session import get_db
from app.models.p1_features import SavedTripCollection, SavedTripCollectionItem, TripJournalEntry, UserNotification
from app.models.public_trip import PublicTripPublication
from app.models.trip import Trip
from app.models.user import User
from app.schemas.p1_features import CollectionCreate, EmergencyOption, EmergencyPreviewRequest, JournalCreate, JournalResponse, NotificationResponse

notifications_router = APIRouter(prefix="/notifications", tags=["Notifications"])
journal_router = APIRouter(prefix="/trips/{trip_id}/journal", tags=["Trip Journal"])
collections_router = APIRouter(prefix="/collections", tags=["Saved Collections"])
emergency_router = APIRouter(prefix="/trips/{trip_id}/emergency", tags=["Emergency Plan"])


@notifications_router.get("")
async def list_notifications(unread_only: bool = False, limit: int = Query(30, ge=1, le=100), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(UserNotification).where(UserNotification.user_id == current_user.id)
    if unread_only:
        stmt = stmt.where(UserNotification.read_at.is_(None))
    result = await db.execute(stmt.order_by(UserNotification.created_at.desc()).limit(limit))
    items = list(result.scalars().all())
    unread = await db.scalar(select(func.count()).select_from(UserNotification).where(UserNotification.user_id == current_user.id, UserNotification.read_at.is_(None)))
    return envelope(data={"items": [NotificationResponse.model_validate(item) for item in items], "unread_count": unread or 0})


@notifications_router.patch("/read-all")
async def read_all_notifications(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserNotification).where(UserNotification.user_id == current_user.id, UserNotification.read_at.is_(None)))
    now = datetime.now(timezone.utc)
    for item in result.scalars().all(): item.read_at = now
    await db.commit()
    return envelope(data=None, message="Đã đánh dấu tất cả là đã đọc")


@notifications_router.patch("/{notification_id}/read")
async def read_notification(notification_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await db.scalar(select(UserNotification).where(UserNotification.id == notification_id, UserNotification.user_id == current_user.id))
    if not item: raise NotFoundError("Không tìm thấy thông báo")
    item.read_at = datetime.now(timezone.utc)
    await db.commit()
    return envelope(data=NotificationResponse.model_validate(item))


@journal_router.get("")
async def list_journal(trip: Trip = Depends(get_trip_read_access), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TripJournalEntry).where(TripJournalEntry.trip_id == trip.id).order_by(TripJournalEntry.entry_date.desc(), TripJournalEntry.created_at.desc()))
    return envelope(data=[JournalResponse.model_validate(item) for item in result.scalars().all()])


@journal_router.post("", status_code=201)
async def create_journal(payload: JournalCreate, trip: Trip = Depends(get_trip_edit_access), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = TripJournalEntry(trip_id=trip.id, user_id=current_user.id, **payload.model_dump())
    db.add(item); await db.commit(); await db.refresh(item)
    return envelope_created(data=JournalResponse.model_validate(item), message="Đã lưu nhật ký chuyến đi")


@journal_router.delete("/{entry_id}")
async def delete_journal(entry_id: uuid.UUID, trip: Trip = Depends(get_trip_edit_access), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await db.scalar(select(TripJournalEntry).where(TripJournalEntry.id == entry_id, TripJournalEntry.trip_id == trip.id, TripJournalEntry.user_id == current_user.id))
    if not item: raise NotFoundError("Không tìm thấy mục nhật ký")
    await db.delete(item); await db.commit(); return envelope(data=None)


@collections_router.get("")
async def list_collections(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SavedTripCollection, func.count(SavedTripCollectionItem.id)).outerjoin(SavedTripCollectionItem).where(SavedTripCollection.user_id == current_user.id).group_by(SavedTripCollection.id).order_by(SavedTripCollection.created_at.desc()))
    return envelope(data=[{"id": str(item.id), "name": item.name, "description": item.description, "created_at": item.created_at, "item_count": count} for item, count in result.all()])


@collections_router.post("", status_code=201)
async def create_collection(payload: CollectionCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = SavedTripCollection(user_id=current_user.id, **payload.model_dump()); db.add(item)
    try: await db.commit()
    except IntegrityError: await db.rollback(); raise AppError("Bạn đã có bộ sưu tập cùng tên")
    await db.refresh(item); return envelope_created(data={"id": str(item.id), "name": item.name, "description": item.description, "created_at": item.created_at, "item_count": 0})


@collections_router.post("/{collection_id}/items/{publication_id}", status_code=201)
async def add_collection_item(collection_id: uuid.UUID, publication_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    collection = await db.scalar(select(SavedTripCollection).where(SavedTripCollection.id == collection_id, SavedTripCollection.user_id == current_user.id))
    publication = await db.scalar(select(PublicTripPublication).where(PublicTripPublication.id == publication_id, PublicTripPublication.status == "published"))
    if not collection or not publication: raise NotFoundError("Không tìm thấy bộ sưu tập hoặc lịch trình")
    db.add(SavedTripCollectionItem(collection_id=collection_id, publication_id=publication_id))
    try: await db.commit()
    except IntegrityError: await db.rollback()
    return envelope_created(data={"added": True})


@emergency_router.post("/preview")
async def emergency_preview(payload: EmergencyPreviewRequest, trip: Trip = Depends(get_trip_read_access)):
    options = {
        "rain": [("Chuyển sang địa điểm trong nhà", "Giữ khung giờ và thay hoạt động ngoài trời."), ("Dời hoạt động", "Chuyển hoạt động sang ngày ít mưa hơn.")],
        "closed": [("Tìm địa điểm tương tự gần đây", "Thay bằng địa điểm cùng loại trong khu vực."), ("Đổi thành thời gian nghỉ", "Giữ lịch trình nhẹ và tránh di chuyển gấp.")],
        "late": [("Rút gọn lịch trình còn lại", "Bỏ hoạt động ưu tiên thấp và giữ các mục đã khóa."), ("Dời hoạt động sang ngày sau", "Giữ nguyên nội dung nhưng thay ngày thực hiện.")],
        "skip": [("Bỏ qua và tối ưu lại tuyến", "Nối hoạt động trước với hoạt động tiếp theo."), ("Thêm địa điểm gần đây", "Lấp khoảng trống bằng lựa chọn gần vị trí hiện tại.")],
        "other": [("Tối ưu lại phần còn lại", "Tạo phương án mới và giữ nguyên các hoạt động đã khóa.")],
    }
    data = [EmergencyOption(id=f"{payload.reason}-{i}", title=title, description=desc, impact="Chỉ là bản xem trước, chưa thay đổi lịch trình") for i, (title, desc) in enumerate(options[payload.reason], 1)]
    return envelope(data=data, message="Hãy chọn và xác nhận trước khi áp dụng")
