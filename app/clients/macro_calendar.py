"""Macro economic calendar client for trade veto windows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.utils.logging import get_logger
from app.utils.time_utils import utcnow

log = get_logger("macro_calendar")

KNOWN_EVENT_TYPES = {"FOMC", "CPI", "NFP"}


class MacroCalendarClient:
    """
    Manages macro event schedule and computes veto windows.

    For v1, uses a manually-maintained schedule seeded at startup.
    Future versions can pull from an API (e.g., FRED, Investing.com scrape).
    """

    def __init__(self, veto_before_min: int = 30, veto_after_min: int = 30):
        self._veto_before = timedelta(minutes=veto_before_min)
        self._veto_after = timedelta(minutes=veto_after_min)
        self._events: list[dict] = []

    def load_events(self, events: list[dict]):
        """Load events — each must have 'event_type', 'title', 'event_time_utc'."""
        self._events = []
        for e in events:
            evt_time = e["event_time_utc"]
            if isinstance(evt_time, str):
                evt_time = datetime.fromisoformat(evt_time).replace(tzinfo=timezone.utc)
            self._events.append({
                **e,
                "event_time_utc": evt_time,
                "veto_start_utc": evt_time - self._veto_before,
                "veto_end_utc": evt_time + self._veto_after,
            })
        log.info("macro_events_loaded", count=len(self._events))

    def is_veto_active(self, now: datetime | None = None) -> tuple[bool, Optional[dict]]:
        """Check if any macro veto window covers the given time."""
        if now is None:
            now = utcnow()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        for e in self._events:
            if e["veto_start_utc"] <= now <= e["veto_end_utc"]:
                return True, e
        return False, None

    def next_veto_event(self, now: datetime | None = None) -> Optional[dict]:
        if now is None:
            now = utcnow()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        future = [e for e in self._events if e["veto_start_utc"] > now]
        if not future:
            return None
        return min(future, key=lambda e: e["veto_start_utc"])

    def get_veto_events_for_db(self) -> list[dict]:
        """Return events formatted for DB insertion."""
        return [
            {
                "event_type": e.get("event_type", ""),
                "source": e.get("source", "manual"),
                "title": e.get("title", ""),
                "event_time_utc": e["event_time_utc"],
                "event_time_local": e.get("event_time_local"),
                "country": e.get("country", "US"),
                "importance": e.get("importance", "high"),
                "veto_start_utc": e["veto_start_utc"],
                "veto_end_utc": e["veto_end_utc"],
            }
            for e in self._events
        ]

    @staticmethod
    def seed_2025_2026_events() -> list[dict]:
        """Hardcoded seed of major macro events for bootstrapping."""
        events = [
            {"event_type": "FOMC", "title": "FOMC Decision", "event_time_utc": "2026-03-18T18:00:00"},
            {"event_type": "FOMC", "title": "FOMC Decision", "event_time_utc": "2026-05-06T18:00:00"},
            {"event_type": "FOMC", "title": "FOMC Decision", "event_time_utc": "2026-06-17T18:00:00"},
            {"event_type": "CPI", "title": "CPI Release", "event_time_utc": "2026-03-12T12:30:00"},
            {"event_type": "CPI", "title": "CPI Release", "event_time_utc": "2026-04-10T12:30:00"},
            {"event_type": "CPI", "title": "CPI Release", "event_time_utc": "2026-05-13T12:30:00"},
            {"event_type": "NFP", "title": "Non-Farm Payrolls", "event_time_utc": "2026-03-06T13:30:00"},
            {"event_type": "NFP", "title": "Non-Farm Payrolls", "event_time_utc": "2026-04-03T12:30:00"},
            {"event_type": "NFP", "title": "Non-Farm Payrolls", "event_time_utc": "2026-05-01T12:30:00"},
        ]
        return events
