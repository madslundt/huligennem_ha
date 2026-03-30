"""Sensor platform for HULiGENNEM — next scheduled live start and end times."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util.dt import parse_datetime

from .const import DOMAIN

_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="planned_starts_at",
        name="Next Live Start",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="planned_ends_at",
        name="Next Live End",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HULiGENNEM sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([
        HuligennemTimestampSensor(coordinator, entry, description)
        for description in _SENSOR_DESCRIPTIONS
    ])


class HuligennemTimestampSensor(CoordinatorEntity, SensorEntity):
    """Sensor exposing a scheduled live start or end timestamp."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the timestamp sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"huligennem_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="HULiGENNEM",
            manufacturer="DR",
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the scheduled timestamp as a datetime object."""
        if self.coordinator.data is None:
            return None
        raw = self.coordinator.data.get(self.entity_description.key)
        if not raw:
            return None
        return parse_datetime(raw)
