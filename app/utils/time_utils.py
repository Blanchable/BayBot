"""Time and date helpers."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_naive() -> datetime:
    return datetime.utcnow()


def tod_bucket(dt: datetime | None = None, bucket_minutes: int = 30) -> str:
    """Return a time-of-day bucket string like '14:30'."""
    if dt is None:
        dt = utcnow()
    minute = (dt.minute // bucket_minutes) * bucket_minutes
    return f"{dt.hour:02d}:{minute:02d}"


def is_within_window(now: datetime, start: datetime, end: datetime) -> bool:
    return start <= now <= end
