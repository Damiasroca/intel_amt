"""Sensor platform for Intel AMT."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IntelAmtCoordinator
from .entity import IntelAmtEntity


@dataclass(frozen=True, kw_only=True)
class IntelAmtInfoSensorDescription:
    """Static hardware/firmware info sensor (from coordinator.device_info)."""

    key: str
    translation_key: str
    icon: str
    value_fn: Callable[[IntelAmtCoordinator], str | None]


INFO_SENSORS: tuple[IntelAmtInfoSensorDescription, ...] = (
    IntelAmtInfoSensorDescription(
        key="model",
        translation_key="model",
        icon="mdi:desktop-tower",
        value_fn=lambda c: c.device_info.model if c.device_info else None,
    ),
    IntelAmtInfoSensorDescription(
        key="serial_number",
        translation_key="serial_number",
        icon="mdi:barcode",
        value_fn=lambda c: c.device_info.serial_number if c.device_info else None,
    ),
    IntelAmtInfoSensorDescription(
        key="amt_firmware",
        translation_key="amt_firmware",
        icon="mdi:chip",
        value_fn=lambda c: c.device_info.amt_version if c.device_info else None,
    ),
    IntelAmtInfoSensorDescription(
        key="bios_version",
        translation_key="bios_version",
        icon="mdi:memory",
        value_fn=lambda c: c.device_info.bios_version if c.device_info else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Intel AMT sensors."""
    coordinator: IntelAmtCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [IntelAmtPowerSensor(coordinator)]
    for description in INFO_SENSORS:
        if description.value_fn(coordinator) is not None:
            entities.append(IntelAmtInfoSensor(coordinator, description))
    async_add_entities(entities)


class IntelAmtPowerSensor(IntelAmtEntity, SensorEntity):
    """AMT power state sensor."""

    _attr_translation_key = "power"
    _attr_icon = "mdi:power-plug"

    def __init__(self, coordinator: IntelAmtCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_power"

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


class IntelAmtInfoSensor(IntelAmtEntity, SensorEntity):
    """Static hardware/firmware info sensor (diagnostic)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: IntelAmtCoordinator,
        description: IntelAmtInfoSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self._description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_translation_key = description.translation_key
        self._attr_icon = description.icon

    @property
    def native_value(self) -> str | None:
        """Return the static value from coordinator.device_info."""
        return self._description.value_fn(self.coordinator)

    @property
    def available(self) -> bool:
        """Info values are read once at setup; always available if we have them."""
        return self._description.value_fn(self.coordinator) is not None
