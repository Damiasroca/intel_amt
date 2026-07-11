"""Config flow for Intel AMT."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .amt_client import AmtClient
from .const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PROTOCOL,
    CONF_USERNAME,
    DEFAULT_PROTOCOL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    PROTOCOL_HTTP,
    PROTOCOL_HTTPS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): vol.In(
            [PROTOCOL_HTTP, PROTOCOL_HTTPS]
        ),
        vol.Optional(CONF_NAME): str,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=30, max=3600)
        ),
    }
)


class IntelAmtConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Intel AMT."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            client = AmtClient(
                host=host,
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                protocol=user_input[CONF_PROTOCOL],
            )

            try:
                await self.hass.async_add_executor_job(client.get_status)
            except Exception:
                _LOGGER.exception("AMT connection test failed")
                errors["base"] = "cannot_connect"
            else:
                name = user_input.get(CONF_NAME) or host
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: host,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_PROTOCOL: user_input[CONF_PROTOCOL],
                        CONF_NAME: name,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Get the options flow."""
        return IntelAmtOptionsFlow()


class IntelAmtOptionsFlow(OptionsFlow):
    """Handle options for Intel AMT."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                {
                    "scan_interval": self.config_entry.options.get(
                        "scan_interval", DEFAULT_SCAN_INTERVAL
                    ),
                },
            ),
        )
