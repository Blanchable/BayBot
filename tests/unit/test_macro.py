"""Unit tests for the macro calendar veto system."""

from datetime import datetime, timedelta, timezone

import pytest

from app.clients.macro_calendar import MacroCalendarClient


@pytest.fixture
def calendar():
    c = MacroCalendarClient(veto_before_min=30, veto_after_min=30)
    c.load_events([
        {
            "event_type": "FOMC",
            "title": "FOMC Decision",
            "event_time_utc": datetime(2026, 3, 18, 18, 0, tzinfo=timezone.utc),
        },
        {
            "event_type": "CPI",
            "title": "CPI Release",
            "event_time_utc": datetime(2026, 3, 12, 12, 30, tzinfo=timezone.utc),
        },
    ])
    return c


class TestMacroCalendar:
    def test_veto_active_during_event(self, calendar):
        t = datetime(2026, 3, 18, 18, 10, tzinfo=timezone.utc)
        active, event = calendar.is_veto_active(t)
        assert active
        assert event["event_type"] == "FOMC"

    def test_veto_active_before_event(self, calendar):
        t = datetime(2026, 3, 18, 17, 35, tzinfo=timezone.utc)
        active, _ = calendar.is_veto_active(t)
        assert active

    def test_veto_inactive_well_before(self, calendar):
        t = datetime(2026, 3, 18, 16, 0, tzinfo=timezone.utc)
        active, _ = calendar.is_veto_active(t)
        assert not active

    def test_veto_inactive_well_after(self, calendar):
        t = datetime(2026, 3, 18, 19, 0, tzinfo=timezone.utc)
        active, _ = calendar.is_veto_active(t)
        assert not active

    def test_next_veto_event(self, calendar):
        t = datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)
        nxt = calendar.next_veto_event(t)
        assert nxt is not None
        assert nxt["event_type"] == "CPI"

    def test_seed_events(self):
        events = MacroCalendarClient.seed_2025_2026_events()
        assert len(events) > 0
        assert all("event_type" in e for e in events)
