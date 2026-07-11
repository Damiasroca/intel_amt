"""Sensor platform for Intel AMT."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .amt_client import AmtStatus
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


@dataclass(frozen=True, kw_only=True)
class IntelAmtStatusSensorDescription:
    """Live status sensor (from coordinator.data / AmtStatus)."""

    key: str
    translation_key: str
    icon: str
    value_fn: Callable[[AmtStatus], str | None]


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
    IntelAmtInfoSensorDescription(
        key="hostname",
        translation_key="hostname",
        icon="mdi:server-network",
        value_fn=lambda c: c.device_info.hostname if c.device_info else None,
    ),
    IntelAmtInfoSensorDescription(
        key="cpu",
        translation_key="cpu",
        icon="mdi:cpu-64-bit",
        value_fn=lambda c: c.device_info.cpu_model if c.device_info else None,
    ),
    IntelAmtInfoSensorDescription(
        key="system_id",
        translation_key="system_id",
        icon="mdi:identifier",
        value_fn=lambda c: c.device_info.platform_guid if c.device_info else None,
    ),
)


STATUS_SENSORS: tuple[IntelAmtStatusSensorDescription, ...] = (
    IntelAmtStatusSensorDescription(
        key="ip_address",
        translation_key="ip_address",
        icon="mdi:ip-network",
        value_fn=lambda s: s.ip_address,
    ),
    IntelAmtStatusSensorDescription(
        key="provisioning_state",
        translation_key="provisioning_state",
        icon="mdi:shield-check",
        value_fn=lambda s: s.provisioning_state,
    ),
    IntelAmtStatusSensorDescription(
        key="provisioning_mode",
        translation_key="provisioning_mode",
        icon="mdi:shield-account",
        value_fn=lambda s: s.provisioning_mode,
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
    for status_description in STATUS_SENSORS:
        entities.append(IntelAmtStatusSensor(coordinator, status_description))
    entities.append(IntelAmtLastEventSensor(coordinator))
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


class IntelAmtStatusSensor(IntelAmtEntity, SensorEntity):
    """Live-status sensor sourced from coordinator.data (AmtStatus)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: IntelAmtCoordinator,
        description: IntelAmtStatusSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self._description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_translation_key = description.translation_key
        self._attr_icon = description.icon

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            return None
        return self._description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self._description.value_fn(self.coordinator.data) is not None
        )


class IntelAmtLastEventSensor(IntelAmtEntity, SensorEntity):
    """Timestamp of the newest AMT event log entry."""

    _attr_translation_key = "last_event"
    _attr_icon = "mdi:history"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: IntelAmtCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_last_event"

    @property
    def native_value(self) -> datetime | None:
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            return None
        raw = self.coordinator.data.last_event_time
        if not raw:
            return None
        try:
            # AMT emits e.g. '2026-07-11T09:43:42Z'.
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            return {}
        return {"description": self.coordinator.data.last_event_description}

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.last_event_time is not None
        )
