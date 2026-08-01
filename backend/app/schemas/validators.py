from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import urlsplit

from pydantic import BeforeValidator, Field


def _strip_text(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


def validated_http_url(value: str | None, error_message: str) -> str | None:
    """Return a normalized absolute HTTP(S) URL or raise a field-friendly error."""
    if value is None:
        return None
    cleaned = value.strip()
    try:
        parsed = urlsplit(cleaned)
        valid = (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not any(character.isspace() or ord(character) < 32 for character in cleaned)
        )
        _ = parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(error_message)
    return cleaned


def is_safe_local_asset_path(value: str) -> bool:
    normalized = value.removeprefix("/")
    return (
        normalized.startswith("assets/")
        and ".." not in normalized.split("/")
        and chr(92) not in normalized
        and "%" not in normalized
    )


TrimmedText = Annotated[str, BeforeValidator(_strip_text)]
ShortListText = Annotated[TrimmedText, Field(min_length=1, max_length=200)]
TagText = Annotated[TrimmedText, Field(min_length=1, max_length=60)]
ParticipantText = Annotated[TrimmedText, Field(min_length=1, max_length=100)]
InterestWeight = Annotated[int, Field(ge=0, le=10)]
PhotoUrlText = Annotated[TrimmedText, Field(min_length=1, max_length=2048)]
