"""
Import toàn bộ models vào đây để Alembic autogenerate detect được hết bảng,
và để đảm bảo SQLAlchemy resolve được các relationship string-based (forward ref).
"""
from app.models.user import User
from app.models.trip import Trip, DayPlan
from app.models.activity import Activity
from app.models.location import Location
from app.models.chat import ChatMessage, AiSuggestion
from app.models.budget import BudgetItem
from app.models.destination_photo import DestinationPhoto
from app.models.refresh_token import RefreshToken

__all__ = [
    "User",
    "Trip",
    "DayPlan",
    "Activity",
    "Location",
    "ChatMessage",
    "AiSuggestion",
    "BudgetItem",
    "DestinationPhoto",
    "RefreshToken",
]
