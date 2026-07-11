"""Config flow for Intel AMT."""

from __future__ import annotations

import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .amt_client import AmtAlarm, AmtClient, AmtError
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

SCAN_INTERVAL_SCHEMA = vol.Schema(
    {
        vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=30, max=3600)
        ),
    }
)


def _default_instance_id() -> str:
    return f"ha-{int(time.time())}"[-32:]


def _alarm_label(alarm: AmtAlarm) -> str:
    label = alarm.element_name or alarm.instance_id
    if alarm.start_time is not None:
        return f"{label} — {alarm.start_time.isoformat()}"
    return label


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

    def _coordinator(self):
        return self.hass.data[DOMAIN][self.config_entry.entry_id]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the options menu."""
        if user_input is not None:
            if user_input == "scan_interval":
                return await self.async_step_scan_interval()
            if user_input == "add_wake_alarm":
                return await self.async_step_add_wake_alarm()
            if user_input == "manage_wake_alarms":
                return await self.async_step_manage_wake_alarms()

        return self.async_show_menu(
            step_id="init",
            menu_options=["scan_interval", "add_wake_alarm", "manage_wake_alarms"],
        )

    async def async_step_scan_interval(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the poll interval."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, **user_input},
            )

        return self.async_show_form(
            step_id="scan_interval",
            data_schema=self.add_suggested_values_to_schema(
                SCAN_INTERVAL_SCHEMA,
                {
                    "scan_interval": self.config_entry.options.get(
                        "scan_interval", DEFAULT_SCAN_INTERVAL
                    ),
                },
            ),
        )

    async def async_step_add_wake_alarm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Schedule a firmware wake alarm."""
        errors: dict[str, str] = {}
        schema = vol.Schema(
            {
                vol.Required("start_time"): cv.datetime,
                vol.Required("instance_id", default=_default_instance_id()): str,
                vol.Optional("element_name"): str,
                vol.Optional("interval_minutes", default=0): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=525600)
                ),
                vol.Optional("delete_on_completion", default=True): cv.boolean,
            }
        )

        if user_input is not None:
            coordinator = self._coordinator()
            try:
                await coordinator.async_add_wake_alarm(
                    start_time=user_input["start_time"],
                    instance_id=user_input["instance_id"],
                    interval_minutes=user_input["interval_minutes"],
                    delete_on_completion=user_input["delete_on_completion"],
                    element_name=user_input.get("element_name"),
                )
            except AmtError:
                _LOGGER.exception("Failed to schedule wake alarm")
                errors["base"] = "cannot_add"
            except Exception:
                _LOGGER.exception("Failed to schedule wake alarm")
                errors["base"] = "cannot_add"
            else:
                return self.async_abort(reason="alarm_scheduled")

        return self.async_show_form(
            step_id="add_wake_alarm",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_manage_wake_alarms(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Delete a scheduled wake alarm."""
        errors: dict[str, str] = {}
        coordinator = self._coordinator()
        await coordinator.async_request_refresh()
        alarms = coordinator.data.wake_alarms if coordinator.data else []

        if not alarms:
            return self.async_abort(reason="no_wake_alarms")

        schema = vol.Schema(
            {
                vol.Required("instance_id"): vol.In(
                    {alarm.instance_id: _alarm_label(alarm) for alarm in alarms}
                ),
            }
        )

        if user_input is not None:
            try:
                await coordinator.async_delete_wake_alarm(user_input["instance_id"])
            except AmtError:
                _LOGGER.exception("Failed to delete wake alarm")
                errors["base"] = "cannot_delete"
            except Exception:
                _LOGGER.exception("Failed to delete wake alarm")
                errors["base"] = "cannot_delete"
            else:
                return self.async_abort(reason="alarm_deleted")

        return self.async_show_form(
            step_id="manage_wake_alarms",
            data_schema=schema,
            errors=errors,
        )
