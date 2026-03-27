"""Tests for HULiGENNEM config flow."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.huligennem.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests in this module."""
    yield


async def test_step_user_show_form(hass: HomeAssistant):
    """Test that the form is shown on first step."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_user_create_entry(hass: HomeAssistant):
    """Test that submitting the form creates an entry."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HULiGENNEM"
    assert result["data"] == {}
