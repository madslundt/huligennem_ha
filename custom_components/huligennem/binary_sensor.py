"""Binary sensor platform for HULiGENNEM — on-air status."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN

_DESCRIPTION = BinarySensorEntityDescription(
    key="on_air",
    name="On Air",
    device_class=BinarySensorDeviceClass.RUNNING,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HULiGENNEM binary sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([HuligennemOnAirBinarySensor(coordinator, entry)])


class HuligennemOnAirBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor tracking whether HULiGENNEM is currently broadcasting live."""

    entity_description = _DESCRIPTION
    _attr_has_entity_name = True
    _attr_unique_id = "huligennem_on_air"

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="HULiGENNEM",
            manufacturer="DR",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True when HULiGENNEM is currently live."""
        if self.coordinator.data is None:
            return None
        return bool(self.coordinator.data.get("on_air", False))
