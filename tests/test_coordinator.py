"""Tests for HULiGENNEM live coordinator event-driven polling logic."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from custom_components.huligennem.coordinator import (
    _MAX_WAIT,
    _POLL_FALLBACK,
    _POST_END_BUFFER,
    _PRE_START_BUFFER,
    _next_interval,
)


class TestNextInterval:
    """Tests for _next_interval."""

    def test_no_data_returns_fallback(self):
        """None data returns the 24-hour fallback."""
        assert _next_interval(None) == _POLL_FALLBACK

    def test_off_air_no_schedule_returns_fallback(self):
        """Off-air with no planned start returns the 24-hour fallback."""
        assert _next_interval({"on_air": False, "planned_starts_at": None}) == _POLL_FALLBACK

    def test_off_air_future_start_polls_one_minute_before(self):
        """Off air with future start → waits until 1 min before planned start."""
        data = {"on_air": False, "planned_starts_at": "2099-01-01T10:00:00.000000Z"}

        with patch("custom_components.huligennem.coordinator.utcnow") as mock_now:
            from homeassistant.util.dt import parse_datetime

            mock_now.return_value = parse_datetime("2099-01-01T01:00:00.000000Z")
            interval = _next_interval(data)

        # 9 hours until start minus 1-minute pre-buffer = 8 h 59 min
        assert interval == timedelta(hours=9) - _PRE_START_BUFFER

    def test_off_air_future_start_capped_at_max_wait(self):
        """Start 30 hours away → interval capped at 24 h."""
        data = {"on_air": False, "planned_starts_at": "2099-01-02T10:00:00.000000Z"}

        with patch("custom_components.huligennem.coordinator.utcnow") as mock_now:
            from homeassistant.util.dt import parse_datetime

            mock_now.return_value = parse_datetime("2099-01-01T04:00:00.000000Z")
            interval = _next_interval(data)

        assert interval == _MAX_WAIT

    def test_off_air_start_already_passed_returns_fallback(self):
        """Start time passed but not on air → 24-hour fallback."""
        data = {"on_air": False, "planned_starts_at": "2000-01-01T10:00:00.000000Z"}

        with patch("custom_components.huligennem.coordinator.utcnow") as mock_now:
            from homeassistant.util.dt import parse_datetime

            mock_now.return_value = parse_datetime("2000-01-01T10:30:00.000000Z")
            interval = _next_interval(data)

        assert interval == _POLL_FALLBACK

    def test_on_air_with_future_end_polls_one_minute_after(self):
        """On air with known end time → waits until 1 min after planned end."""
        data = {"on_air": True, "planned_ends_at": "2099-01-01T12:00:00.000000Z"}

        with patch("custom_components.huligennem.coordinator.utcnow") as mock_now:
            from homeassistant.util.dt import parse_datetime

            mock_now.return_value = parse_datetime("2099-01-01T10:00:00.000000Z")
            interval = _next_interval(data)

        # 2 hours until end plus 1-minute post-buffer = 2 h 01 min
        assert interval == timedelta(hours=2) + _POST_END_BUFFER

    def test_on_air_end_already_passed_returns_fallback(self):
        """On air but end time already passed → 24-hour fallback."""
        data = {"on_air": True, "planned_ends_at": "2000-01-01T10:00:00.000000Z"}

        with patch("custom_components.huligennem.coordinator.utcnow") as mock_now:
            from homeassistant.util.dt import parse_datetime

            mock_now.return_value = parse_datetime("2000-01-01T11:00:00.000000Z")
            interval = _next_interval(data)

        assert interval == _POLL_FALLBACK

    def test_on_air_no_end_time_returns_fallback(self):
        """On air with no end time → 24-hour fallback."""
        assert _next_interval({"on_air": True, "planned_ends_at": None}) == _POLL_FALLBACK

    def test_on_air_end_capped_at_max_wait(self):
        """End time 30 hours away → interval capped at 24 h."""
        data = {"on_air": True, "planned_ends_at": "2099-01-02T12:00:00.000000Z"}

        with patch("custom_components.huligennem.coordinator.utcnow") as mock_now:
            from homeassistant.util.dt import parse_datetime

            mock_now.return_value = parse_datetime("2099-01-01T10:00:00.000000Z")
            interval = _next_interval(data)

        assert interval == _MAX_WAIT
