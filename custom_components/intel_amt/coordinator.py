"""Data update coordinator for Intel AMT."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .amt_client import AmtClient, AmtDeviceInfo, AmtStatus
from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PROTOCOL,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


class IntelAmtCoordinator(DataUpdateCoordinator[AmtStatus]):
    """Poll AMT power status."""

    config_entry: ConfigEntry
    device_info: AmtDeviceInfo | None = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: AmtClient) -> None:
        self.client = client
        scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_HOST]}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.config_entry = entry

    async def _async_update_data(self) -> AmtStatus:
        try:
            return await self.hass.async_add_executor_job(self.client.get_status)
        except Exception as err:
            raise UpdateFailed(f"AMT status poll failed: {err}") from err

    async def async_run_power(self, action: str) -> None:
        """Run a power action and refresh coordinator data."""
        await self.hass.async_add_executor_job(self.client.set_power, action)
        await self.async_request_refresh()

    async def async_pxe_boot(self) -> None:
        """PXE boot and refresh coordinator data."""
        await self.hass.async_add_executor_job(self.client.pxe_boot)
        await self.async_request_refresh()

    async def async_add_wake_alarm(
        self,
        start_time: datetime,
        instance_id: str,
        interval_minutes: int = 0,
        delete_on_completion: bool = True,
        element_name: str | None = None,
    ) -> None:
        """Schedule a firmware wake and refresh."""
        await self.hass.async_add_executor_job(
            self.client.add_wake_alarm,
            start_time,
            instance_id,
            interval_minutes,
            delete_on_completion,
            element_name,
        )
        await self.async_request_refresh()

    async def async_delete_wake_alarm(self, instance_id: str) -> None:
        """Delete a wake alarm and refresh."""
        await self.hass.async_add_executor_job(
            self.client.delete_wake_alarm, instance_id
        )
        await self.async_request_refresh()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Intel AMT from a config entry."""
    client = AmtClient(
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        protocol=entry.data[CONF_PROTOCOL],
    )

    coordinator = IntelAmtCoordinator(hass, entry, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        raise
    except Exception as err:
        raise ConfigEntryNotReady(f"Unable to connect to AMT: {err}") from err

    try:
        coordinator.device_info = await hass.async_add_executor_job(
            client.get_device_info
        )
    except Exception as err:
        _LOGGER.warning("AMT device info fetch failed (continuing without): %s", err)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Intel AMT config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
