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
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.activity import Activity
from app.models.budget import BudgetItem
from app.models.chat import AiSuggestion, ChatMessage
from app.models.trip import DayPlan, Trip
from app.models.user import User
from app.services import trip_history_service

_groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)


class AiActivityPayload(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    type: str = "other"
    start_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    estimated_cost: int | None = Field(default=None, ge=0, le=1_000_000_000)
    notes: str | None = Field(default=None, max_length=2000)
    location_ref: str | None = Field(default=None, max_length=20)
    reason: str | None = Field(default=None, max_length=1000)
    travel_note: str | None = Field(default=None, max_length=1000)

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        return value if value in {"meal", "attraction", "hotel", "transport", "other"} else "other"


class AiDayPayload(BaseModel):
    day_number: int = Field(ge=1, le=366)
    activities: list[AiActivityPayload] = Field(default_factory=list, max_length=30)


class AiItineraryPayload(BaseModel):
    days: list[AiDayPayload] = Field(default_factory=list, max_length=366)


class AiExtractedActivityPayload(BaseModel):
    has_activity: bool
    day_number: int = Field(default=1, ge=1, le=366)
    activity: AiActivityPayload | None = None

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


async def _build_trip_context(db: AsyncSession, trip: Trip, max_activities: int = 80) -> str:
    day_result = await db.execute(
        select(DayPlan)
        .where(DayPlan.trip_id == trip.id)
        .options(selectinload(DayPlan.activities).selectinload(Activity.location))
        .order_by(DayPlan.day_number)
    )
    days = list(day_result.scalars().all())

    budget_result = await db.execute(
        select(BudgetItem).where(BudgetItem.trip_id == trip.id).order_by(BudgetItem.created_at.desc())
    )
    budget_items = list(budget_result.scalars().all())

    lines = [
        "Ngu canh du lieu hien tai trong he thong. Khi tra loi, hay bam sat du lieu nay neu nguoi dung hoi ve lich trinh, chi phi, hoac muon chinh sua chuyen di.",
        "Lich trinh hien tai:",
    ]

    if not days:
        lines.append("- Chua co day plan nao.")
    else:
        activity_count = 0
        for day in days:
            lines.append(f"- Ngay {day.day_number} ({day.date.isoformat()}):")
            if not day.activities:
                lines.append("  - Chua co hoat dong.")
                continue
            for activity in day.activities:
                if activity_count >= max_activities:
                    lines.append("  - Da rut gon bot hoat dong do lich trinh qua dai.")
                    break
                time_text = _format_activity_time(activity.start_time, activity.end_time)
                location_text = f" tai {activity.location.name}" if activity.location else ""
                cost_text = f", chi phi {activity.estimated_cost} VND" if activity.estimated_cost else ""
                lines.append(
                    f"  - {time_text}{activity.title}{location_text} "
                    f"({activity.type or 'other'}{cost_text})."
                )
                activity_count += 1
            if activity_count >= max_activities:
                break

    total_itinerary_cost = sum(
        int(activity.estimated_cost or 0)
        for day in days
        for activity in day.activities
    )
    lines.append(f"Tong chi phi uoc tinh tu lich trinh: {total_itinerary_cost} VND.")

    if budget_items:
        planned = sum(int(item.planned_amount or 0) for item in budget_items)
        actual = sum(int(item.actual_amount or 0) for item in budget_items)
        lines.append(f"Ngan sach items: planned={planned} VND, actual={actual} VND.")
        for item in budget_items[:12]:
            lines.append(
                f"- Budget {item.category}: {item.label}, planned {item.planned_amount} VND, actual {item.actual_amount} VND."
            )
    else:
        lines.append("Chua co budget item chi tiet.")

    lines.append(
        "Neu de xuat thay doi lich trinh, hay noi ro ngay, hoat dong bi anh huong, ly do, va tac dong den chi phi/thoi gian."
    )
    return "\n".join(lines)


def _format_activity_time(start_time: str | None, end_time: str | None) -> str:
    if start_time and end_time:
        return f"{start_time}-{end_time}: "
    if start_time:
        return f"{start_time}: "
    return ""


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
    trip_context = await _build_trip_context(db, trip)
    completion = await _groq_client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "system", "content": f"{_build_system_prompt(trip)}\n\n{trip_context}"}, *history],
    )
    ai_text = completion.choices[0].message.content or ""

    assistant_msg = await _save_message(db, trip.id, "assistant", ai_text)

    suggestion = None
    # 1. Trích xuất gợi ý thêm vào lịch trình trước
    itinerary_sug = await _extract_itinerary_suggestion(user_message, ai_text)
    if itinerary_sug:
        act = itinerary_sug["activities"][0]
        itinerary_sug["title"] = f"Gợi ý thêm: {act.get('title')}"
        itinerary_sug["description"] = f"Thời gian: {act.get('start_time')} - Ngày {itinerary_sug.get('day_number')}. {act.get('description', '')}"
        itinerary_sug["estimated_cost"] = act.get("estimated_cost")

        suggestion = AiSuggestion(trip_id=trip.id, type="itinerary", content_json=itinerary_sug, status="pending")
        db.add(suggestion)
        await db.commit()
        await db.refresh(suggestion)
    else:
        # Fallback sang gợi ý địa điểm thông thường
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
    trip_context = await _build_trip_context(db, trip)

    full_text = ""
    stream = await _groq_client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "system", "content": f"{_build_system_prompt(trip)}\n\n{trip_context}"}, *history],
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
    # 1. Trích xuất gợi ý thêm vào lịch trình trước
    itinerary_sug = await _extract_itinerary_suggestion(user_message, full_text)
    if itinerary_sug:
        act = itinerary_sug["activities"][0]
        itinerary_sug["title"] = f"Gợi ý thêm: {act.get('title')}"
        itinerary_sug["description"] = f"Thời gian: {act.get('start_time')} - Ngày {itinerary_sug.get('day_number')}. {act.get('description', '')}"
        itinerary_sug["estimated_cost"] = act.get("estimated_cost")

        suggestion = AiSuggestion(trip_id=trip.id, type="itinerary", content_json=itinerary_sug, status="pending")
        db.add(suggestion)
        await db.commit()
        await db.refresh(suggestion)
        suggestion_id = str(suggestion.id)
    else:
        # Fallback sang gợi ý địa điểm thông thường
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


async def get_suggestion_editable_or_404(db: AsyncSession, suggestion_id: uuid.UUID, user_id: uuid.UUID) -> AiSuggestion:
    from app.core.exceptions import ForbiddenError, NotFoundError
    from app.services import trip_share_service

    result = await db.execute(select(AiSuggestion).where(AiSuggestion.id == suggestion_id))
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise NotFoundError("Khong tim thay goi y nay")
    if not await trip_share_service.user_can_edit_trip(db, suggestion.trip_id, user_id):
        raise ForbiddenError("Ban khong co quyen cap nhat goi y nay")
    return suggestion


async def update_suggestion_status(
    db: AsyncSession,
    suggestion: AiSuggestion,
    new_status: str,
    actor: User,
) -> int:
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
                title=activity_data.get("title", "Hoạt động"),
                description=activity_data.get("description"),
                type=activity_data.get("type", "other"),
                start_time=activity_data.get("start_time"),
                end_time=activity_data.get("end_time"),
                estimated_cost=activity_data.get("estimated_cost"),
                notes=activity_data.get("notes"),
                order_index=next_order_index,
            )
            db.add(new_activity)
            next_order_index += 1
            activities_created += 1

        if activities_created:
            await trip_history_service.record_history_event(
                db,
                trip_id=suggestion.trip_id,
                actor_user_id=actor.id,
                entity_type="ai_suggestion",
                entity_id=suggestion.id,
                action="applied",
                summary=f"Da ap dung goi y AI va them {activities_created} hoat dong",
                metadata={
                    "suggestion_type": suggestion.type,
                    "day_number": day_number,
                    "activities_created": activities_created,
                },
            )

    await db.commit()
    return activities_created



_ITINERARY_GENERATION_PROMPT = """Bạn là trợ lý du lịch AI chuyên nghiệp, am hiểu sâu sắc về du lịch Việt Nam.
Hãy lập lịch trình chi tiết từng ngày cho chuyến đi này:
- Điểm đến: {destination}
- Thời gian: Từ {start_date} đến {end_date} ({total_days} ngày)
- Ngân sách dự kiến: {budget} VND cho {num_travelers} người
- Sở thích và ghi chú bổ sung: {preferences}

Yêu cầu định dạng đầu ra:
Bạn phải trả về một JSON Object duy nhất có cấu trúc chính xác như sau:
{{
  "days": [
    {{
      "day_number": 1,
      "activities": [
        {{
          "title": "Tên hoạt động hoặc địa điểm tham quan",
          "description": "Mô tả chi tiết hoạt động này (khoảng 2-4 câu), nêu rõ lý do nên đi và nét đặc sắc.",
          "type": "meal | attraction | hotel | transport | other",
          "start_time": "HH:MM",
          "end_time": "HH:MM",
          "estimated_cost": 50000,
          "notes": "Lưu ý, kinh nghiệm thực tế, món ăn nên gọi hoặc kinh nghiệm chọn giờ đi"
        }}
      ]
    }}
  ]
}}

Lưu ý cực kỳ quan trọng để lập lịch trình siêu chi tiết và thực tế:
1. ĐỊA ĐIỂM ĂN UỐNG CHI TIẾT: Các bữa ăn (loại "meal") phải là các quán ăn, nhà hàng, quán cà phê CỤ THỂ, NỔI TIẾNG, CÓ THẬT và được đánh giá cao tại {destination}. Không được ghi chung chung như "Ăn sáng", "Ăn trưa", "Đi uống cà phê". Phải ghi rõ tên quán và địa chỉ/khu vực (Ví dụ: "Ăn sáng Mỳ Quảng Bà Mua tại 95A Nguyễn Tri Phương", "Uống cà phê tại Cộng Cà Phê - 98-96 Bạch Đằng", "Ăn tối Hải sản Năm Đảnh tại K139/H59/38 Trần Quang Khải").
2. GIÁ CẢ THỰC TẾ: Hãy ước lượng chi phí (estimated_cost) thực tế và hợp lý bằng VND cho từng hoạt động:
   - Đối với quán ăn/cà phê: Ước lượng số tiền trung bình một người hoặc cả nhóm tiêu dùng tại quán đó (Ví dụ: ăn sáng mỳ Quảng 40,000 - 60,000 VND/người, ăn hải sản 150,000 - 300,000 VND/người).
   - Đối với địa điểm tham quan: Nếu có bán vé (như Bà Nà Hills, Ngũ Hành Sơn), phải ghi đúng giá vé hiện tại của người lớn nhân với số người ({num_travelers} người). Nếu miễn phí, ghi 0.
   - Đối với di chuyển: Ghi ước lượng chi phí taxi/Grab dự kiến.
3. PHÂN BỔ THỜI GIAN: Thời gian hoạt động (start_time và end_time) phải logic, phù hợp với thời gian di chuyển thực tế giữa các điểm tại {destination}.
4. Trường "type" chỉ được phép nhận một trong các giá trị: "meal", "attraction", "hotel", "transport", "other".
5. Trường "start_time" và "end_time" phải ở định dạng "HH:MM" (Ví dụ: "08:30", "12:00", "18:00").
6. YÊU CẦU DI CHUYỂN & LƯU TRÚ BẮT BUỘC: Lịch trình phải bao gồm đầy đủ hoạt động di chuyển và nghỉ ngơi:
   - Ngày 1: Phải có hoạt động di chuyển từ sân bay/nhà ga đến khách sạn (loại "transport") và hoạt động check-in khách sạn cụ thể (loại "hotel").
   - Mỗi tối: Phải có hoạt động lưu trú/nghỉ đêm tại khách sạn cụ thể (loại "hotel") vào cuối ngày (khoảng 21:00 - 22:00 trở đi).
   - Ngày cuối: Phải có hoạt động check-out khách sạn cụ thể (loại "hotel") và di chuyển ra sân bay/nhà ga ra về (loại "transport").
7. Chỉ trả về đúng chuỗi JSON, tuyệt đối không bao bọc bằng markdown block hay giải thích gì thêm."""


async def generate_itinerary_with_ai(trip: Trip) -> dict:
    """Gọi Groq AI lập lịch trình chuyến đi và trả về JSON chứa chi tiết hoạt động các ngày."""
    if not settings.GROQ_API_KEY:
        raise AppError(
            "Vui lòng cấu hình GROQ_API_KEY trong file .env để sử dụng tính năng lập lịch trình AI.",
            status_code=400,
        )

    total_days = (trip.end_date - trip.start_date).days + 1
    system_prompt = "You are a travel assistant that plans itineraries and outputs JSON format."
    user_prompt = _ITINERARY_GENERATION_PROMPT.format(
        destination=trip.destination,
        start_date=trip.start_date.isoformat(),
        end_date=trip.end_date.isoformat(),
        total_days=total_days,
        budget=trip.budget or "không giới hạn",
        num_travelers=trip.num_travelers,
        preferences=trip.preferences or "không có yêu cầu đặc biệt",
    )

    try:
        completion = await _groq_client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content or ""
        parsed = AiItineraryPayload.model_validate(json.loads(content))
        return parsed.model_dump()
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"Invalid AI itinerary payload: {e}")
        raise AppError(
            "AI tra ve lich trinh khong dung dinh dang. Vui long thu lai sau.",
            status_code=502,
        )
    except Exception as e:
        print(f"Error in generate_itinerary_with_ai: {e}")
        raise AppError(
            "Không thể lập lịch trình bằng AI lúc này. Vui lòng kiểm tra lại cấu hình GROQ_API_KEY hoặc thử lại sau.",
            status_code=500,
        )


_EXTRACT_ACTIVITY_PROMPT = """Bạn là trợ lý AI chuyên phân tích hội thoại du lịch.
Hãy phân tích tin nhắn của người dùng và câu trả lời của trợ lý để xác định xem người dùng có yêu cầu thêm hoạt động/lịch trình cụ thể nào vào chuyến đi hay không (ví dụ: thuê xe máy, ăn tối ở nhà hàng X, đi tham quan địa điểm Y).

Nếu có yêu cầu thêm hoạt động, hãy trả về một JSON Object có cấu trúc chính xác như sau:
{{
  "has_activity": true,
  "day_number": 1,
  "activity": {{
    "title": "Tên hoạt động (ví dụ: Thuê xe máy tại cửa hàng X)",
    "description": "Mô tả ngắn gọn hoạt động (1-2 câu)",
    "type": "meal | attraction | hotel | transport | other",
    "start_time": "HH:MM",
    "end_time": "HH:MM",
    "estimated_cost": 150000,
    "notes": "Lưu ý hoặc ghi chú thêm"
  }}
}}

Nếu không có hoạt động nào được yêu cầu thêm hoặc thông tin không rõ ràng, hãy trả về:
{{
  "has_activity": false
}}

Lưu ý:
1. "day_number" phải là số nguyên đại diện cho ngày muốn thêm (ví dụ: 1, 2, 3). Nếu không nói rõ ngày nào, hãy mặc định là 1.
2. "type" chỉ được phép nhận một trong các giá trị: "meal", "attraction", "hotel", "transport", "other". (Thuê xe máy/taxi/vé bay là "transport", khách sạn là "hotel", nhà hàng là "meal", điểm chơi là "attraction").
3. Trả về đúng định dạng JSON, tuyệt đối không giải thích gì thêm."""


async def _extract_itinerary_suggestion(user_msg: str, ai_msg: str) -> dict | None:
    """Phân tích tin nhắn để trích xuất hoạt động người dùng muốn thêm vào lịch trình."""
    if not settings.GROQ_API_KEY:
        return None
    try:
        prompt = f"User message: {user_msg}\nAI message: {ai_msg}"
        completion = await _groq_client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _EXTRACT_ACTIVITY_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        res = AiExtractedActivityPayload.model_validate(json.loads(completion.choices[0].message.content or "{}"))
        if res.has_activity and res.activity:
            activity = res.activity.model_dump()
            return {
                "day_number": res.day_number,
                "activities": [activity]
            }
    except Exception as e:
        print(f"Error extracting activity suggestion: {e}")
    return None


_GROUNDED_ITINERARY_PROMPT = """You are a senior travel itinerary planner for Vietnamese users.
Return exactly one JSON object. Do not use markdown.

Trip:
- Destination: {destination}
- Dates: {start_date} to {end_date}
- Total days: {total_days}
- Travelers: {num_travelers}
- Budget: {budget_text}
- Budget rule: total estimated_cost should stay within 115% of budget when budget exists.
- Pace: {pace}
- Budget mode: {budget_mode}
- User place priority: {prioritize_user_places}
- Preferred transport mode: {transport_mode}
- Departure location: {departure_location}
- Departure time: {departure_time}
- Estimated travel hours to destination: {estimated_travel_hours}
- Arrival transport to destination: {arrival_transport}
- Daily active window: {daily_window}
- User preferences: {preferences}
- User profile interests: {interests}
- User requested places, balanced priority: {must_visit}
- Places to avoid: {avoid_places}
- Dietary notes: {dietary_notes}
- Mobility notes: {mobility_notes}

Grounded place candidates:
{candidate_json}

Validation errors from previous attempt:
{validation_errors}

Rules:
1. Use only the place candidates above for attraction, meal, cafe, and hotel activities.
2. Any place-based activity must include location_ref matching a candidate ref, for example "p3".
3. Transport/rest/check-in/check-out activities may omit location_ref.
4. Each day must have logical, non-overlapping HH:MM start_time and end_time.
5. Include famous attractions and the user's requested places when route, time, and budget make sense.
6. Keep travel realistic by grouping nearby places on the same day when possible.
   - Nearby attractions can be combined into 2-3 visits in one full day.
   - Far attractions should reduce the number of visits and include more travel/rest buffer.
7. Costs are VND for the whole group, not per person.
8. Respect places to avoid, dietary notes, mobility notes, pace, and the daily active window.
9. For strict budget mode, stay under budget. For flexible_15, stay within 115% of budget. For comfort, prioritize fit and route quality while keeping costs reasonable.
10. Use departure_time and estimated_travel_hours when provided. If travel crosses midnight, split the timeline into the correct day_number. Never create an activity whose end_time is earlier than or equal to start_time on the same day.
11. Build a closed-loop day flow, not just a list of places:
   - Day 1 must start with travel from departure location to the destination. If arrival is next day, Day 1 should mainly contain the departure/travel segment and any realistic meal before departure.
   - Arrival day must include arrival, homestay/hotel check-in or luggage drop, rest, then meals/activities only if time still makes sense.
   - Middle/full days must start from lodging, include breakfast, 1-2 morning attractions if close, lunch, rest, 1-2 afternoon attractions if close, return to lodging, dinner, optional cafe/night walk, and overnight rest.
   - Last day must include checkout, final light attraction/meal if time allows, and travel back/out of the destination.
12. Avoid repeating the same attraction route on multiple days unless the user explicitly requested it.
13. Do not produce logistics-only full days. A day with enough time at destination should contain real travel experiences: sightseeing, food, cafe/night walk, local culture, or light entertainment.
14. Every activity should have realistic group cost. Include arrival/departure transport, local transport, lodging per night, meals, tickets/activities, and small buffer costs.
15. Output schema:
{{
  "days": [
    {{
      "day_number": 1,
      "activities": [
        {{
          "title": "Concrete activity title",
          "description": "Short useful description",
          "type": "meal | attraction | hotel | transport | other",
          "start_time": "08:30",
          "end_time": "10:00",
          "estimated_cost": 100000,
          "location_ref": "p1",
          "reason": "Why this fits the trip",
          "travel_note": "Route or timing note",
          "notes": "Practical tips"
        }}
      ]
    }}
  ]
}}"""


def _format_daily_window(start_time: str | None, end_time: str | None) -> str:
    if start_time and end_time:
        return f"{start_time} to {end_time}"
    if start_time:
        return f"start after {start_time}"
    if end_time:
        return f"finish before {end_time}"
    return "not specified"


async def generate_grounded_itinerary_with_ai(
    trip: Trip,
    candidates: list[dict],
    *,
    pace: str,
    must_visit: list[str],
    interests: list[str],
    avoid_places: list[str] | None = None,
    budget_mode: str = "flexible_15",
    prioritize_user_places: str = "balanced",
    transport_mode: str = "mixed",
    departure_location: str | None = None,
    departure_time: str | None = None,
    estimated_travel_hours: float | None = None,
    arrival_transport: str | None = None,
    daily_start_time: str | None = None,
    daily_end_time: str | None = None,
    dietary_notes: str | None = None,
    mobility_notes: str | None = None,
    validation_errors: list[str] | None = None,
) -> dict:
    """Generate an itinerary constrained to known location candidates."""
    if not settings.GROQ_API_KEY:
        raise AppError(
            "Vui long cau hinh GROQ_API_KEY de su dung tinh nang lap lich trinh AI.",
            status_code=400,
        )

    total_days = (trip.end_date - trip.start_date).days + 1
    compact_candidates = [
        {
            "ref": item.get("ref"),
            "name": item.get("name"),
            "category": item.get("category"),
            "address": item.get("address"),
            "lat": item.get("lat"),
            "lng": item.get("lng"),
            "rating": item.get("rating"),
            "score": item.get("score"),
            "must_visit_match": item.get("must_visit_match"),
        }
        for item in candidates[:45]
    ]

    prompt = _GROUNDED_ITINERARY_PROMPT.format(
        destination=trip.destination,
        start_date=trip.start_date.isoformat(),
        end_date=trip.end_date.isoformat(),
        total_days=total_days,
        num_travelers=trip.num_travelers,
        budget_text=f"{trip.budget} VND" if trip.budget else "no fixed budget",
        pace=pace,
        budget_mode=budget_mode,
        prioritize_user_places=prioritize_user_places,
        transport_mode=transport_mode,
        departure_location=departure_location or "not specified",
        departure_time=departure_time or "not specified",
        estimated_travel_hours=(
            f"{estimated_travel_hours:g} hours" if estimated_travel_hours is not None else "not specified"
        ),
        arrival_transport=arrival_transport or transport_mode or "not specified",
        daily_window=_format_daily_window(daily_start_time, daily_end_time),
        preferences=trip.preferences or "none",
        interests=", ".join(interests) if interests else "none",
        must_visit=", ".join(must_visit) if must_visit else "none",
        avoid_places=", ".join(avoid_places or []) if avoid_places else "none",
        dietary_notes=dietary_notes or "none",
        mobility_notes=mobility_notes or "none",
        candidate_json=json.dumps(compact_candidates, ensure_ascii=False),
        validation_errors="; ".join(validation_errors or []) or "none",
    )

    try:
        completion = await _groq_client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You produce grounded travel itinerary JSON only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content or ""
        parsed = AiItineraryPayload.model_validate(json.loads(content))
        return parsed.model_dump()
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"Invalid grounded AI itinerary payload: {e}")
        raise AppError("AI tra ve lich trinh khong dung dinh dang.", status_code=502)
    except AppError:
        raise
    except Exception as e:
        print(f"Error in generate_grounded_itinerary_with_ai: {e}")
        raise AppError("Khong the lap lich trinh bang AI luc nay.", status_code=500)
