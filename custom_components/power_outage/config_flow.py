"""Config flow for LOE Power Outage."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, FlowResult

from .const import (
    ALL_GROUPS,
    CONF_GROUPS,
    CONF_INTERVAL,
    CONF_URL,
    DEFAULT_INTERVAL,
    DEFAULT_URL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): str,
        vol.Required(CONF_INTERVAL, default=DEFAULT_INTERVAL): int,
        vol.Required(CONF_GROUPS, default=ALL_GROUPS): vol.All(
            vol.Length(min=1),
            [vol.In(ALL_GROUPS)],
        ),
    }
)


class LOEPowerOutageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for LOE Power Outage."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input.get(CONF_URL, "")
            if not (url.startswith("http://") or url.startswith("https://")):
                errors[CONF_URL] = "invalid_url"

            if not errors:
                return self.async_create_entry(
                    title="LOE Power Outage", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
