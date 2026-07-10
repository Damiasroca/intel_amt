"""Switch platform for Intel AMT."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IntelAmtCoordinator
from .entity import IntelAmtEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Intel AMT switch."""
    coordinator: IntelAmtCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IntelAmtPowerSwitch(coordinator)])


class IntelAmtPowerSwitch(IntelAmtEntity, SwitchEntity):
    """AMT power switch (on / soft-off)."""

    _attr_translation_key = "power"
    _attr_icon = "mdi:desktop-tower"

    @property
    def is_on(self) -> bool | None:
        """Return true if machine is powered on."""
        if not self.coordinator.last_update_success:
            return None
        return self.coordinator.data.power_state == "on"

    async def async_turn_on(self, **kwargs) -> None:
        """Power on."""
        await self.coordinator.async_run_power("on")

    async def async_turn_off(self, **kwargs) -> None:
        """Graceful shutdown (requires Intel LMS in the OS)."""
        await self.coordinator.async_run_power("soft-off")
