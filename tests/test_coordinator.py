"""Tests for HULiGENNEM live coordinator dynamic polling logic."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from custom_components.huligennem.coordinator import (
    _MAX_WAIT,
    _POLL_ACTIVE,
    _POLL_NO_SCHEDULE,
    _PRE_START_BUFFER,
    _next_interval,
)


def _iso(dt_str: str) -> str:
    """Return an ISO 8601 UTC string as-is (helper for readability)."""
    return dt_str


class TestNextInterval:
    """Tests for _next_interval."""

    def test_no_data_returns_no_schedule_poll(self):
        """None data falls back to the no-schedule interval."""
        assert _next_interval(None) == _POLL_NO_SCHEDULE

    def test_on_air_returns_active_poll(self):
        """On-air state triggers the 60-second active poll."""
        data = {"on_air": True, "planned_starts_at": None}
        assert _next_interval(data) == _POLL_ACTIVE

    def test_no_schedule_returns_no_schedule_poll(self):
        """Off-air with no planned start falls back to the no-schedule interval."""
        data = {"on_air": False, "planned_starts_at": None}
        assert _next_interval(data) == _POLL_NO_SCHEDULE

    def test_start_in_far_future_returns_reduced_interval(self):
        """Start 9 hours away → wait ≈ 8h 55min (time_until - 5min buffer)."""
        future = "2099-01-01T12:00:00.000000Z"
        data = {"on_air": False, "planned_starts_at": future}

        with patch("custom_components.huligennem.coordinator.utcnow") as mock_now:
            from homeassistant.util.dt import parse_datetime

            mock_now.return_value = parse_datetime("2099-01-01T03:00:00.000000Z")
            interval = _next_interval(data)

        expected = timedelta(hours=9) - _PRE_START_BUFFER
        assert interval == expected

    def test_start_far_future_capped_at_max_wait(self):
        """Start 20 hours away → interval capped at _MAX_WAIT (12 h)."""
        future = "2099-01-01T23:00:00.000000Z"
        data = {"on_air": False, "planned_starts_at": future}

        with patch("custom_components.huligennem.coordinator.utcnow") as mock_now:
            from homeassistant.util.dt import parse_datetime

            mock_now.return_value = parse_datetime("2099-01-01T03:00:00.000000Z")
            interval = _next_interval(data)

        assert interval == _MAX_WAIT

    def test_start_within_near_window_returns_active_poll(self):
        """Start 5 minutes away (within the 10-min window) → active poll."""
        future = "2099-01-01T10:05:00.000000Z"
        data = {"on_air": False, "planned_starts_at": future}

        with patch("custom_components.huligennem.coordinator.utcnow") as mock_now:
            from homeassistant.util.dt import parse_datetime

            mock_now.return_value = parse_datetime("2099-01-01T10:00:00.000000Z")
            interval = _next_interval(data)

        assert interval == _POLL_ACTIVE

    def test_start_already_passed_returns_active_poll(self):
        """Start time in the past but not on air → poll actively (show may be late)."""
        past = "2000-01-01T10:00:00.000000Z"
        data = {"on_air": False, "planned_starts_at": past}

        with patch("custom_components.huligennem.coordinator.utcnow") as mock_now:
            from homeassistant.util.dt import parse_datetime

            mock_now.return_value = parse_datetime("2000-01-01T10:30:00.000000Z")
            interval = _next_interval(data)

        assert interval == _POLL_ACTIVE

    def test_start_exactly_at_near_window_boundary_returns_active_poll(self):
        """Start exactly 10 minutes away → within window → active poll."""
        future = "2099-01-01T10:10:00.000000Z"
        data = {"on_air": False, "planned_starts_at": future}

        with patch("custom_components.huligennem.coordinator.utcnow") as mock_now:
            from homeassistant.util.dt import parse_datetime

            mock_now.return_value = parse_datetime("2099-01-01T10:00:00.000000Z")
            interval = _next_interval(data)

        assert interval == _POLL_ACTIVE
