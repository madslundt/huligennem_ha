"""Tests for HULiGENNEM __init__."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.huligennem import (
    PLATFORMS,
    HuligennemRuntimeData,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.huligennem.api import HuligennemApiError


@pytest.mark.asyncio
async def test_async_setup_entry():
    """Test successful setup creates runtime data with api and coordinator."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    entry = MagicMock()
    entry.runtime_data = None

    with (
        patch("custom_components.huligennem.async_get_clientsession"),
        patch("custom_components.huligennem.HuligennemAPI") as mock_api_class,
        patch("custom_components.huligennem.HuligennemLiveCoordinator") as mock_coord_class,
        patch(
            "custom_components.huligennem.async_register_services",
            new_callable=AsyncMock,
        ) as mock_register,
    ):
        mock_api = AsyncMock()
        mock_api.async_get_series = AsyncMock(return_value=[])
        mock_api.async_get_live_status = AsyncMock(return_value={"on_air": False})
        mock_api_class.return_value = mock_api

        mock_coordinator = AsyncMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coord_class.return_value = mock_coordinator

        result = await async_setup_entry(hass, entry)

        assert result is True
        assert isinstance(entry.runtime_data, HuligennemRuntimeData)
        assert entry.runtime_data.api is mock_api
        assert entry.runtime_data.coordinator is mock_coordinator
        mock_api.async_get_series.assert_awaited_once()
        mock_coordinator.async_config_entry_first_refresh.assert_awaited_once()
        hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(entry, PLATFORMS)
        mock_register.assert_awaited_once_with(hass)


@pytest.mark.asyncio
async def test_async_setup_entry_connection_error():
    """Test setup fails with ConfigEntryNotReady on connection error."""
    hass = MagicMock()
    entry = MagicMock()
    entry.runtime_data = None

    with (
        patch("custom_components.huligennem.async_get_clientsession"),
        patch("custom_components.huligennem.HuligennemAPI") as mock_api_class,
    ):
        mock_api = AsyncMock()
        mock_api.async_get_series = AsyncMock(side_effect=HuligennemApiError("Connection refused"))
        mock_api_class.return_value = mock_api

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_async_setup_entry_live_failure_continues():
    """Test setup proceeds even if initial live status fetch fails."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    entry = MagicMock()
    entry.runtime_data = None

    with (
        patch("custom_components.huligennem.async_get_clientsession"),
        patch("custom_components.huligennem.HuligennemAPI") as mock_api_class,
        patch("custom_components.huligennem.HuligennemLiveCoordinator") as mock_coord_class,
        patch("custom_components.huligennem.async_register_services", new_callable=AsyncMock),
    ):
        mock_api = AsyncMock()
        mock_api.async_get_series = AsyncMock(return_value=[])
        mock_api_class.return_value = mock_api

        mock_coordinator = AsyncMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=ConfigEntryNotReady("live down")
        )
        mock_coord_class.return_value = mock_coordinator

        result = await async_setup_entry(hass, entry)

        assert result is True
        assert isinstance(entry.runtime_data, HuligennemRuntimeData)


@pytest.mark.asyncio
async def test_async_unload_entry():
    """Test successful unload unregisters services and unloads platforms."""
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    entry = MagicMock()

    with patch("custom_components.huligennem.unregister_services") as mock_unregister:
        result = await async_unload_entry(hass, entry)

        assert result is True
        mock_unregister.assert_called_once_with(hass)
        hass.config_entries.async_unload_platforms.assert_awaited_once_with(entry, PLATFORMS)
