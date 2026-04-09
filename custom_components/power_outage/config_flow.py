"""Config flow for LOE Power Outage."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_INTERVAL, CONF_URL, DEFAULT_INTERVAL, DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): str,
        vol.Required(CONF_INTERVAL, default=DEFAULT_INTERVAL): int,
    }
)


async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
    """Handle a flow initiated by the user."""
    errors: dict[str, str] = {}

    if user_input is not None:
        url = user_input.get(CONF_URL, "")
        if not (url.startswith("http://") or url.startswith("https://")):
            errors[CONF_URL] = "invalid_url"

        if not errors:
            return self.async_create_entry(title="LOE Power Outage", data=user_input)

    return self.async_show_form(
        step_id="user",
        data_schema=STEP_USER_DATA_SCHEMA,
        errors=errors,
    )
