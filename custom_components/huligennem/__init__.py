"""The HULiGENNEM integration for Home Assistant.

Provides media browsing and playback of Danish children's podcasts and
live radio from dererhuligennem.dk via the Media Source platform.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HuligennemAPI, HuligennemApiError
from .const import DOMAIN as DOMAIN
from .coordinator import HuligennemLiveCoordinator
from .services import async_register_services, unregister_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


@dataclass
class HuligennemRuntimeData:
    """Runtime data stored in the config entry."""

    api: HuligennemAPI
    coordinator: HuligennemLiveCoordinator


type HuligennemConfigEntry = ConfigEntry[HuligennemRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: HuligennemConfigEntry) -> bool:
    """Set up HULiGENNEM from a config entry.

    Creates the API client, warms the series cache, sets up a coordinator
    for live-status polling, and registers services and sensor platforms.

    Raises:
        ConfigEntryNotReady: If the initial connection to the platform fails.

    """
    session = async_get_clientsession(hass)
    api = HuligennemAPI(session)

    try:
        await api.async_get_series()
    except HuligennemApiError as err:
        raise ConfigEntryNotReady(f"Failed to connect to HULiGENNEM: {err}") from err

    coordinator = HuligennemLiveCoordinator(hass, api, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        _LOGGER.warning("Could not fetch initial live status; will retry on next poll")

    entry.runtime_data = HuligennemRuntimeData(api=api, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HuligennemConfigEntry) -> bool:
    """Unload a HULiGENNEM config entry and clean up services and platforms."""
    unregister_services(hass)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
