"""Service handlers for the HULiGENNEM integration.

Provides three services:
- ``huligennem.search_series``: Search/filter the series catalog.
- ``huligennem.get_episodes``: Get all episodes for a given series.
- ``huligennem.get_live``: Get current live stream information.

All services return response data directly (``SupportsResponse.ONLY``).
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse

from .api import HuligennemAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_SEARCH_SERIES = "search_series"
SERVICE_GET_EPISODES = "get_episodes"
SERVICE_GET_LIVE = "get_live"

SCHEMA_SEARCH_SERIES = vol.Schema(
    {
        vol.Optional("query"): str,
    }
)

SCHEMA_GET_EPISODES = vol.Schema(
    {
        vol.Required("serie_id"): int,
    }
)

SCHEMA_GET_LIVE = vol.Schema({})


def get_api(hass: HomeAssistant) -> HuligennemAPI:
    """Get the API instance from the active config entry.

    Args:
        hass: The Home Assistant instance.

    Returns:
        The HuligennemAPI stored in the config entry's runtime_data.

    Raises:
        ValueError: If no HULiGENNEM config entry is loaded.

    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise ValueError("HULiGENNEM integration not configured")
    return entries[0].runtime_data


async def async_handle_search_series(call: ServiceCall) -> ServiceResponse:
    """Handle the ``search_series`` service call.

    Fetches all series and optionally filters by a case-insensitive
    substring match on the title.

    Returns:
        Dict with a ``series`` key containing a list of matching series.

    """
    api = get_api(call.hass)
    series = await api.async_get_series()

    query = call.data.get("query")
    if query:
        query_lower = query.lower()
        series = [s for s in series if query_lower in s.get("title", "").lower()]

    return {
        "series": [
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "slug": s.get("slug"),
                "poster_url": s.get("poster", {}).get("media_url")
                if s.get("poster")
                else None,
            }
            for s in series
        ]
    }


async def async_handle_get_episodes(call: ServiceCall) -> ServiceResponse:
    """Handle the ``get_episodes`` service call.

    Fetches the playlist for the given series and returns a flat list
    of all episodes across all seasons.

    Returns:
        Dict with an ``episodes`` key containing episode details.

    """
    api = get_api(call.hass)
    serie_id: int = call.data["serie_id"]
    playlist = await api.async_get_playlist(serie_id)

    episodes: list[dict[str, Any]] = []
    for season in playlist.get("data", {}).get("seasons", []):
        for ep in season.get("episodes", []):
            media = ep.get("media", {})
            episodes.append(
                {
                    "id": ep.get("id"),
                    "title": ep.get("title"),
                    "season": season.get("title"),
                    "media_url": media.get("url"),
                    "duration_seconds": media.get("duration_in_seconds"),
                }
            )

    return {"episodes": episodes}


async def async_handle_get_live(call: ServiceCall) -> ServiceResponse:
    """Handle the ``get_live`` service call.

    Returns:
        Dict with live stream details if available, or
        ``{"available": False}`` if no stream is active.

    """
    api = get_api(call.hass)
    live = await api.async_get_live()

    if live:
        return {
            "available": True,
            "title": live.get("title"),
            "stream_url": live.get("stream_url"),
            "planned_starts_at": live.get("planned_starts_at"),
            "planned_ends_at": live.get("planned_ends_at"),
        }

    return {"available": False}


async def async_register_services(hass: HomeAssistant) -> None:
    """Register all HULiGENNEM services.

    Guarded against duplicate registration — safe to call on reload.
    """
    if hass.services.has_service(DOMAIN, SERVICE_SEARCH_SERIES):
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_SERIES,
        async_handle_search_series,
        schema=SCHEMA_SEARCH_SERIES,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_EPISODES,
        async_handle_get_episodes,
        schema=SCHEMA_GET_EPISODES,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_LIVE,
        async_handle_get_live,
        schema=SCHEMA_GET_LIVE,
        supports_response=SupportsResponse.ONLY,
    )


def unregister_services(hass: HomeAssistant) -> None:
    """Remove all HULiGENNEM services from the service registry."""
    hass.services.async_remove(DOMAIN, SERVICE_SEARCH_SERIES)
    hass.services.async_remove(DOMAIN, SERVICE_GET_EPISODES)
    hass.services.async_remove(DOMAIN, SERVICE_GET_LIVE)
