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
from app.models.account_token import AccountToken
from app.models.trip_share import TripParticipant, TripShareInvite
from app.models.trip_history import TripHistoryEvent
from app.models.public_trip import (
    ActivityPublicationSource,
    PublicTripImport,
    PublicTripPublication,
    PublicTripSave,
)
from app.models.p1_features import UserNotification, TripJournalEntry, SavedTripCollection, SavedTripCollectionItem
from app.models.p2_features import PublicTripComment, PublicTripRating, AuthorFollow, HiddenRecommendation, CommunityReport, TourBookingInquiry
from app.models.rate_limit import ApiRateLimitBucket

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
    "AccountToken",
    "TripParticipant",
    "TripShareInvite",
    "TripHistoryEvent",
    "PublicTripPublication",
    "PublicTripSave",
    "PublicTripImport",
    "ActivityPublicationSource",
    "UserNotification",
    "TripJournalEntry",
    "SavedTripCollection",
    "SavedTripCollectionItem",
    "PublicTripComment",
    "PublicTripRating",
    "AuthorFollow",
    "HiddenRecommendation",
    "CommunityReport",
    "TourBookingInquiry",
    "ApiRateLimitBucket",
]
