# Smart Travel Planner — Backend API

FastAPI + PostgreSQL + Groq AI + OpenStreetMap. Implement đầy đủ 32 endpoints theo `api_spec.md`.

## Cấu trúc project

```
app/
├── main.py                      # Entry point, đăng ký router + middleware
├── core/
│   ├── config.py                # Settings đọc từ .env
│   ├── security.py              # JWT + bcrypt
│   ├── deps.py                  # get_current_user, get_owned_trip
│   ├── exceptions.py            # AppError + global exception handlers
│   └── response.py              # envelope() — wrapper {status_code, message, data}
├── db/
│   └── session.py                # Async engine + get_db()
├── models/                       # SQLAlchemy ORM (8 bảng)
│   ├── user.py
│   ├── trip.py                   # Trip + DayPlan
│   ├── activity.py
│   ├── location.py
│   ├── chat.py                   # ChatMessage + AiSuggestion
│   └── budget.py
├── schemas/                      # Pydantic request/response (theo từng module)
│   ├── auth.py
│   ├── user.py
│   ├── trip.py
│   ├── day_plan.py
│   ├── location.py
│   ├── budget.py
│   └── chat.py
├── services/                     # Business logic (KHÔNG import FastAPI)
│   ├── auth_service.py
│   ├── user_service.py
│   ├── trip_service.py
│   ├── activity_service.py
│   ├── location_service.py       # OpenStreetMap: Nominatim + Overpass
│   ├── budget_service.py
│   └── ai_service.py             # Groq API — non-stream + SSE stream
└── api/routers/                  # FastAPI routes — file mỏng, chỉ gọi service
    ├── auth_router.py
    ├── user_router.py
    ├── trip_router.py
    ├── activity_router.py
    ├── location_router.py
    ├── budget_router.py
    └── chat_router.py
```

## Cài đặt

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Sửa .env: DATABASE_URL, JWT_SECRET_KEY, GROQ_API_KEY
```

## Tạo database

```bash
# Tạo DB postgres tên smart_travel trước, sau đó:
alembic init alembic              # nếu chưa có
alembic revision --autogenerate -m "init schema"
alembic upgrade head
```

Hoặc đơn giản hơn cho đồ án — tạo bảng trực tiếp từ models:

```python
# scripts/create_tables.py
import asyncio
from app.db.session import engine, Base
from app import models  # import để đăng ký toàn bộ model

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(main())
```

```bash
python -m scripts.create_tables
```

## Chạy server

```bash
uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

## Biến môi trường quan trọng

| Biến | Mô tả |
|------|-------|
| `DATABASE_URL` | Connection string PostgreSQL (asyncpg driver) |
| `JWT_SECRET_KEY` | Khóa bí mật ký JWT — đổi giá trị random khi deploy |
| `GROQ_API_KEY` | API key từ console.groq.com (bắt buộc cho module AI Chat) |
| `GROQ_MODEL` | Mặc định `llama-3.3-70b-versatile` |

## Lưu ý kỹ thuật

- **Response format**: mọi endpoint trả về qua `envelope()` đúng chuẩn `{status_code, message, data}` — kể cả lỗi 400/401/403/404/422/500 (xử lý tập trung trong `core/exceptions.py`).
- **Locations module**: dùng OpenStreetMap (Nominatim cho text search, Overpass cho nearby search) — hoàn toàn miễn phí, không cần API key Google Places.
- **AI Chat streaming**: `POST /trips/{id}/chat` với `stream: true` trả về `StreamingResponse` định dạng SSE (`text/event-stream`), đúng format trong spec.
- **Quyền truy cập**: mọi route có `{trip_id}` dùng dependency `get_owned_trip` để tự động kiểm tra trip thuộc về user hiện tại, raise 403 nếu không phải.
