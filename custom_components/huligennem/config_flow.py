"""Config flow for the HULiGENNEM integration.

This is a confirmation-only flow — no user input is required since
the integration has no configurable options (no auth, no settings).
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class HuligennemConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HULiGENNEM.

    Since the integration requires no credentials or configuration,
    this flow simply shows a confirmation form and creates the entry.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step.

        Shows a confirmation form. On submit, creates a config entry
        with an empty data dict.
        """
        if user_input is not None:
            return self.async_create_entry(title="HULiGENNEM", data={})

        return self.async_show_form(step_id="user")
