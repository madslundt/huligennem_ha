"""The HULiGENNEM integration for Home Assistant.

Provides media browsing and playback of Danish children's podcasts and
live radio from dererhuligennem.dk via the Media Source platform.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HuligennemAPI, HuligennemApiError
from .const import DOMAIN as DOMAIN
from .services import async_register_services, unregister_services

_LOGGER = logging.getLogger(__name__)

type HuligennemConfigEntry = ConfigEntry[HuligennemAPI]


async def async_setup_entry(hass: HomeAssistant, entry: HuligennemConfigEntry) -> bool:
    """Set up HULiGENNEM from a config entry.

    Creates the API client, warms the series cache, and registers services.

    Raises:
        ConfigEntryNotReady: If the initial connection to the platform fails.

    """
    session = async_get_clientsession(hass)
    api = HuligennemAPI(session)

    try:
        await api.async_get_series()
    except HuligennemApiError as err:
        raise ConfigEntryNotReady(f"Failed to connect to HULiGENNEM: {err}") from err

    entry.runtime_data = api
    await async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HuligennemConfigEntry) -> bool:
    """Unload a HULiGENNEM config entry and clean up services."""
    unregister_services(hass)
    return True
