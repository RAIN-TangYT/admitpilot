"""Shared time helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""

    return datetime.now(UTC)


def utc_today() -> date:
    """Return today's UTC date."""

    return utc_now().date()


def ensure_utc(value: datetime) -> datetime:
    """Normalize a datetime into timezone-aware UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_iso_utc(value: datetime | None = None) -> str:
    """Serialize a datetime as an ISO 8601 UTC string."""

    return ensure_utc(value or utc_now()).isoformat()
