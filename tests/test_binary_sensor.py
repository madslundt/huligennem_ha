"""Tests for HULiGENNEM binary sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.huligennem.binary_sensor import HuligennemOnAirBinarySensor


@pytest.fixture
def coordinator():
    """Create a mock coordinator."""
    coord = MagicMock()
    coord.data = {
        "on_air": True,
        "title": "Live Show",
        "stream_url": "https://example.com/live.m3u8",
    }
    return coord


@pytest.fixture
def entry():
    """Create a mock config entry."""
    e = MagicMock()
    e.entry_id = "test_entry_id"
    return e


@pytest.fixture
def sensor(coordinator, entry):
    """Create the binary sensor."""
    return HuligennemOnAirBinarySensor(coordinator, entry)


class TestHuligennemOnAirBinarySensor:
    """Tests for HuligennemOnAirBinarySensor."""

    def test_is_on_when_on_air(self, sensor, coordinator):
        """Test sensor returns True when on_air is True."""
        coordinator.data = {"on_air": True}
        assert sensor.is_on is True

    def test_is_off_when_not_on_air(self, sensor, coordinator):
        """Test sensor returns False when on_air is False."""
        coordinator.data = {"on_air": False}
        assert sensor.is_on is False

    def test_is_none_when_no_data(self, sensor, coordinator):
        """Test sensor returns None when coordinator has no data yet."""
        coordinator.data = None
        assert sensor.is_on is None

    def test_device_class(self, sensor):
        """Test binary sensor has RUNNING device class."""
        assert sensor.device_class == BinarySensorDeviceClass.RUNNING

    def test_unique_id(self, sensor):
        """Test binary sensor has the expected unique ID."""
        assert sensor.unique_id == "huligennem_on_air"

    def test_has_entity_name(self, sensor):
        """Test binary sensor uses entity naming convention."""
        assert sensor._attr_has_entity_name is True
