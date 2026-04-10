"""Data update coordinator for HULiGENNEM live status with event-driven polling.

Rather than a fixed interval, the next refresh is scheduled based on when
a state change is expected:

- Off air, future start known        → poll 1 min before planned start (max 24 h)
- On air, future end known           → poll 1 min after planned end (max 24 h)
- Off air, start in the past/unknown → poll every 1 h (stale/missing schedule)
- On air, end in the past/unknown    → poll every 1 h (overrun or no schedule)
- Anything else                      → poll every 24 h (minimum once a day)
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import parse_datetime, utcnow

from .api import HuligennemAPI

_LOGGER = logging.getLogger(__name__)

_PRE_START_BUFFER = timedelta(minutes=1)
_POST_END_BUFFER = timedelta(minutes=1)
_POLL_FALLBACK = timedelta(hours=24)    # used when data is None (initial/unknown state)
_POLL_NO_SCHEDULE = timedelta(hours=1)  # used when schedule is stale or unknown
_MAX_WAIT = timedelta(hours=24)         # cap on calculated waits (independent of _POLL_FALLBACK)


def _next_interval(data: dict[str, Any] | None) -> timedelta:
    """Return how long to wait before the next live-status refresh."""
    if data is None:
        return _POLL_FALLBACK

    now = utcnow()

    if data.get("on_air"):
        planned_ends_raw = data.get("planned_ends_at")
        if planned_ends_raw:
            planned_ends = parse_datetime(planned_ends_raw)
            if planned_ends:
                wait = (planned_ends + _POST_END_BUFFER) - now
                if wait.total_seconds() > 0:
                    return min(wait, _MAX_WAIT)
        # End time unknown or already passed — poll hourly to detect when show ends
        return _POLL_NO_SCHEDULE

    planned_starts_raw = data.get("planned_starts_at")
    if planned_starts_raw:
        planned_starts = parse_datetime(planned_starts_raw)
        if planned_starts:
            wait = (planned_starts - _PRE_START_BUFFER) - now
            if wait.total_seconds() > 0:
                return min(wait, _MAX_WAIT)

    # Start is in the past or not scheduled yet — poll hourly to pick up new schedule
    return _POLL_NO_SCHEDULE


class HuligennemLiveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls at expected state-change times."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: HuligennemAPI,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator with a default interval of 24 hours."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="huligennem_live",
            update_method=api.async_get_live_status,
            update_interval=_POLL_FALLBACK,
        )

    def _schedule_refresh(self) -> None:
        """Override to schedule next refresh at the expected state-change time."""
        self.update_interval = _next_interval(self.data)
        _LOGGER.debug("Next live-status poll in %s", self.update_interval)
        super()._schedule_refresh()
