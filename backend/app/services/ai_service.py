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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.activity import Activity
from app.models.chat import AiSuggestion, ChatMessage
from app.models.trip import DayPlan, Trip

_groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)

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
    completion = await _groq_client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "system", "content": _build_system_prompt(trip)}, *history],
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

    full_text = ""
    stream = await _groq_client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "system", "content": _build_system_prompt(trip)}, *history],
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


async def update_suggestion_status(db: AsyncSession, suggestion: AiSuggestion, new_status: str) -> int:
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
        return json.loads(content)
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
        res = json.loads(completion.choices[0].message.content)
        if res.get("has_activity") and res.get("activity"):
            activity = res["activity"]
            return {
                "day_number": res.get("day_number", 1),
                "activities": [activity]
            }
    except Exception as e:
        print(f"Error extracting activity suggestion: {e}")
    return None


