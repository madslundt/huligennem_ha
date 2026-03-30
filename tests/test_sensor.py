"""Tests for HULiGENNEM sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import SensorDeviceClass

from custom_components.huligennem.sensor import _SENSOR_DESCRIPTIONS, HuligennemTimestampSensor


@pytest.fixture
def coordinator():
    """Create a mock coordinator with scheduled times."""
    coord = MagicMock()
    coord.data = {
        "planned_starts_at": "2026-03-27T14:00:00.000000Z",
        "planned_ends_at": "2026-03-27T17:00:00.000000Z",
    }
    return coord


@pytest.fixture
def entry():
    """Create a mock config entry."""
    e = MagicMock()
    e.entry_id = "test_entry_id"
    return e


@pytest.fixture
def start_sensor(coordinator, entry):
    """Create the next live start sensor."""
    return HuligennemTimestampSensor(coordinator, entry, _SENSOR_DESCRIPTIONS[0])


@pytest.fixture
def end_sensor(coordinator, entry):
    """Create the next live end sensor."""
    return HuligennemTimestampSensor(coordinator, entry, _SENSOR_DESCRIPTIONS[1])


class TestHuligennemTimestampSensor:
    """Tests for HuligennemTimestampSensor."""

    def test_start_parses_iso_datetime(self, start_sensor):
        """Test that next live start parses ISO 8601 datetime correctly."""
        value = start_sensor.native_value
        assert value is not None
        assert value.hour == 14
        assert value.tzinfo is not None

    def test_end_parses_iso_datetime(self, end_sensor):
        """Test that next live end parses ISO 8601 datetime correctly."""
        value = end_sensor.native_value
        assert value is not None
        assert value.hour == 17
        assert value.tzinfo is not None

    def test_start_returns_none_when_no_data(self, start_sensor, coordinator):
        """Test start sensor returns None when coordinator has no data."""
        coordinator.data = None
        assert start_sensor.native_value is None

    def test_end_returns_none_when_no_data(self, end_sensor, coordinator):
        """Test end sensor returns None when coordinator has no data."""
        coordinator.data = None
        assert end_sensor.native_value is None

    def test_start_returns_none_when_field_absent(self, start_sensor, coordinator):
        """Test start sensor returns None when field is not in coordinator data."""
        coordinator.data = {}
        assert start_sensor.native_value is None

    def test_device_class(self, start_sensor, end_sensor):
        """Test both sensors have TIMESTAMP device class."""
        assert start_sensor.device_class == SensorDeviceClass.TIMESTAMP
        assert end_sensor.device_class == SensorDeviceClass.TIMESTAMP

    def test_distinct_unique_ids(self, start_sensor, end_sensor):
        """Test sensors have distinct unique IDs containing their key."""
        assert start_sensor.unique_id != end_sensor.unique_id
        assert "planned_starts_at" in start_sensor.unique_id
        assert "planned_ends_at" in end_sensor.unique_id

    def test_has_entity_name(self, start_sensor, end_sensor):
        """Test sensors use entity naming convention."""
        assert start_sensor._attr_has_entity_name is True
        assert end_sensor._attr_has_entity_name is True
