"""Service handlers for Intel AMT."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .amt_client import AmtError
from .const import DOMAIN, SERVICE_ADD_WAKE_ALARM, SERVICE_DELETE_WAKE_ALARM
from .coordinator import IntelAmtCoordinator

_LOGGER = logging.getLogger(__name__)

ADD_WAKE_ALARM_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required("start_time"): cv.datetime,
        vol.Required("instance_id"): cv.string,
        vol.Optional("interval_minutes", default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0)
        ),
        vol.Optional("delete_on_completion", default=True): cv.boolean,
        vol.Optional("element_name"): cv.string,
    }
)

DELETE_WAKE_ALARM_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required("instance_id"): cv.string,
    }
)


def _resolve_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> IntelAmtCoordinator | None:
    """Resolve the coordinator from a service call target."""
    if call.target_device_ids:
        device_registry = dr.async_get(hass)
        for device_id in call.target_device_ids:
            device = device_registry.async_get(device_id)
            if device is None:
                continue
            for domain, entry_id in device.identifiers:
                if domain == DOMAIN:
                    return hass.data[DOMAIN].get(entry_id)

    if call.target_entities:
        entity_registry = er.async_get(hass)
        for entity_id in call.target_entities:
            entry = entity_registry.async_get(entity_id)
            if entry and entry.config_entry_id:
                coordinator = hass.data[DOMAIN].get(entry.config_entry_id)
                if coordinator is not None:
                    return coordinator

    return None


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Intel AMT services once."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_WAKE_ALARM):
        return

    async def add_wake_alarm(call: ServiceCall) -> None:
        coordinator = _resolve_coordinator(hass, call)
        if coordinator is None:
            raise HomeAssistantError(
                "No Intel AMT device matched. Target a device or entity from this integration."
            )
        try:
            await coordinator.async_add_wake_alarm(
                start_time=call.data["start_time"],
                instance_id=call.data["instance_id"],
                interval_minutes=call.data["interval_minutes"],
                delete_on_completion=call.data["delete_on_completion"],
                element_name=call.data.get("element_name"),
            )
        except AmtError as err:
            raise HomeAssistantError(str(err)) from err

    async def delete_wake_alarm(call: ServiceCall) -> None:
        coordinator = _resolve_coordinator(hass, call)
        if coordinator is None:
            raise HomeAssistantError(
                "No Intel AMT device matched. Target a device or entity from this integration."
            )
        try:
            await coordinator.async_delete_wake_alarm(call.data["instance_id"])
        except AmtError as err:
            raise HomeAssistantError(str(err)) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_WAKE_ALARM,
        add_wake_alarm,
        schema=ADD_WAKE_ALARM_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_WAKE_ALARM,
        delete_wake_alarm,
        schema=DELETE_WAKE_ALARM_SCHEMA,
    )


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister services when the last config entry is removed."""
    if hass.data.get(DOMAIN):
        return
    for service in (SERVICE_ADD_WAKE_ALARM, SERVICE_DELETE_WAKE_ALARM):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
