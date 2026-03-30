"""Data update coordinator for HULiGENNEM live status with dynamic polling.

Instead of a fixed interval, the next refresh is scheduled based on the
data returned from the last fetch:

- On air                              → every 60 s (monitor for end)
- Off air, start ≤ 10 min away        → every 60 s (imminent broadcast)
- Off air, start already passed       → every 60 s (show may be running late)
- Off air, start > 10 min away        → wait until 5 min before start (max 12 h)
- Off air, no scheduled start         → every 4 h (check for new events)
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

_POLL_ACTIVE = timedelta(seconds=60)
_NEAR_START_WINDOW = timedelta(minutes=10)
_PRE_START_BUFFER = timedelta(minutes=5)
_POLL_NO_SCHEDULE = timedelta(hours=4)
_MAX_WAIT = timedelta(hours=12)


def _next_interval(data: dict[str, Any] | None) -> timedelta:
    """Return how long to wait before the next live-status refresh."""
    if data is None:
        return _POLL_NO_SCHEDULE

    if data.get("on_air"):
        return _POLL_ACTIVE

    planned_start_raw = data.get("planned_starts_at")
    if planned_start_raw:
        planned_start = parse_datetime(planned_start_raw)
        if planned_start:
            time_until_start = planned_start - utcnow()
            if time_until_start <= timedelta(0):
                # Start time passed but not on air — may be running late
                return _POLL_ACTIVE
            if time_until_start <= _NEAR_START_WINDOW:
                # Within 10 minutes of scheduled start
                return _POLL_ACTIVE
            # Sleep until 5 min before start, capped to catch reschedules
            return min(time_until_start - _PRE_START_BUFFER, _MAX_WAIT)

    return _POLL_NO_SCHEDULE


class HuligennemLiveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that adjusts its poll interval based on the live schedule."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: HuligennemAPI,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator with a default interval of 4 hours."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="huligennem_live",
            update_method=api.async_get_live_status,
            update_interval=_POLL_NO_SCHEDULE,
        )

    def _schedule_refresh(self) -> None:
        """Override to compute a dynamic interval after each refresh."""
        self.update_interval = _next_interval(self.data)
        _LOGGER.debug("Next live-status poll in %s", self.update_interval)
        super()._schedule_refresh()
