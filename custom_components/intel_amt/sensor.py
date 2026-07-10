"""Sensor platform for Intel AMT."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
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
    """Set up Intel AMT sensor."""
    coordinator: IntelAmtCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IntelAmtPowerSensor(coordinator)])


class IntelAmtPowerSensor(IntelAmtEntity, SensorEntity):
    """AMT power state sensor."""

    _attr_translation_key = "power"
    _attr_icon = "mdi:power-plug"

    @property
    def native_value(self) -> str | None:
        """Return current power state."""
        if not self.coordinator.last_update_success:
            return None
        return self.coordinator.data.power_state

    @property
    def extra_state_attributes(self) -> dict:
        """Return available transitions."""
        if not self.coordinator.last_update_success:
            return {}
        return {
            "available_transitions": self.coordinator.data.available_transitions,
        }

    @property
    def available(self) -> bool:
        """Return availability."""
        return self.coordinator.last_update_success
