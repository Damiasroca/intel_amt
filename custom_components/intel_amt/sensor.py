"""Sensor platform for Intel AMT."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from homeassistant.components.recorder import get_instance
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .amt_client import AmtAlarm, AmtStatus
from .const import DOMAIN
from .coordinator import IntelAmtCoordinator
from .entity import IntelAmtEntity
from .uptime import UPTIME_WINDOW, compute_power_uptime, uptime_ratio_percent


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
    power_sensor = IntelAmtPowerSensor(coordinator)
    entities: list[SensorEntity] = [
        power_sensor,
        IntelAmtPowerUptimeSensor(hass, coordinator, power_sensor),
    ]
    for description in INFO_SENSORS:
        if description.value_fn(coordinator) is not None:
            entities.append(IntelAmtInfoSensor(coordinator, description))
    for status_description in STATUS_SENSORS:
        entities.append(IntelAmtStatusSensor(coordinator, status_description))
    entities.append(IntelAmtLastEventSensor(coordinator))
    entities.append(IntelAmtNextWakeSensor(coordinator))
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


class IntelAmtPowerUptimeSensor(IntelAmtEntity, SensorEntity):
    """Percentage of the last 24h spent in the powered-on state."""

    _attr_translation_key = "power_uptime_24h"
    _attr_icon = "mdi:chart-donut"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: IntelAmtCoordinator,
        power_sensor: IntelAmtPowerSensor,
    ) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._power_sensor = power_sensor
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_power_uptime_24h"
        self._attr_available = False

    async def async_added_to_hass(self) -> None:
        """Refresh when the power sensor changes or on coordinator poll."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._power_sensor.entity_id], self._async_power_state_changed
            )
        )
        await self._async_update_uptime()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Recompute uptime on each status poll."""
        self.hass.async_create_task(self._async_update_uptime())
        super()._handle_coordinator_update()

    @callback
    def _async_power_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Recompute uptime immediately when power state changes."""
        self.hass.async_create_task(self._async_update_uptime())

    async def _async_update_uptime(self) -> None:
        """Query recorder history and update the percentage."""
        power_entity_id = self._power_sensor.entity_id
        if power_entity_id is None:
            self._attr_native_value = None
            self._attr_available = False
            self.async_write_ha_state()
            return

        if get_instance(self.hass) is None:
            self._attr_native_value = None
            self._attr_available = False
            self.async_write_ha_state()
            return

        stats = await self.hass.async_add_executor_job(
            compute_power_uptime,
            self.hass,
            power_entity_id,
        )
        if stats is None:
            self._attr_native_value = None
            self._attr_available = False
        else:
            self._attr_native_value = uptime_ratio_percent(stats)
            self._attr_available = True
            self._attr_extra_state_attributes = {
                "hours_on": round(stats.seconds_on / 3600, 2),
                "window_hours": round(stats.period_seconds / 3600, 2),
                "window": str(UPTIME_WINDOW),
            }
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Available when recorder history can be computed."""
        return self._attr_available


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


def _alarm_to_dict(alarm: AmtAlarm) -> dict:
    """Serialize an AmtAlarm for sensor attributes."""
    return {
        "instance_id": alarm.instance_id,
        "element_name": alarm.element_name,
        "start_time": alarm.start_time.isoformat() if alarm.start_time else None,
        "interval": alarm.interval,
        "delete_on_completion": alarm.delete_on_completion,
    }


class IntelAmtNextWakeSensor(IntelAmtEntity, SensorEntity):
    """Earliest scheduled firmware wake time and full alarm list."""

    _attr_translation_key = "next_wake"
    _attr_icon = "mdi:alarm"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: IntelAmtCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_next_wake"

    @property
    def native_value(self) -> datetime | None:
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            return None
        return self.coordinator.data.next_wake_time

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            return {}
        alarms = self.coordinator.data.wake_alarms
        return {
            "wake_alarm_count": len(alarms),
            "wake_alarms": [_alarm_to_dict(alarm) for alarm in alarms],
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success
