"""Intel AMT integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import async_setup_entry as _setup_coordinator
from .coordinator import async_unload_entry as _unload_coordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Intel AMT from a config entry."""
    result = await _setup_coordinator(hass, entry)
    if result:
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return result


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Intel AMT config entry."""
    return await _unload_coordinator(hass, entry)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    return True
