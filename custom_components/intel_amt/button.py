"""Button platform for Intel AMT."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .amt_client import AmtAlarm
from .const import DOMAIN
from .coordinator import IntelAmtCoordinator
from .entity import IntelAmtEntity


@dataclass(frozen=True, kw_only=True)
class IntelAmtButtonDescription:
    """Describes an Intel AMT button."""

    key: str
    translation_key: str
    icon: str
    press_fn: Callable[[IntelAmtCoordinator], Coroutine[Any, Any, None]]


async def _power_on(coordinator: IntelAmtCoordinator) -> None:
    await coordinator.async_run_power("on")


async def _hard_off(coordinator: IntelAmtCoordinator) -> None:
    await coordinator.async_run_power("off")


async def _soft_off(coordinator: IntelAmtCoordinator) -> None:
    await coordinator.async_run_power("soft-off")


async def _hard_reset(coordinator: IntelAmtCoordinator) -> None:
    await coordinator.async_run_power("reset")


async def _soft_reset(coordinator: IntelAmtCoordinator) -> None:
    await coordinator.async_run_power("soft-reset")


async def _reboot(coordinator: IntelAmtCoordinator) -> None:
    await coordinator.async_run_power("reboot")


async def _pxe_boot(coordinator: IntelAmtCoordinator) -> None:
    await coordinator.async_pxe_boot()


async def _refresh(coordinator: IntelAmtCoordinator) -> None:
    await coordinator.async_request_refresh()


BUTTONS: tuple[IntelAmtButtonDescription, ...] = (
    IntelAmtButtonDescription(
        key="power_on",
        translation_key="power_on",
        icon="mdi:power",
        press_fn=_power_on,
    ),
    IntelAmtButtonDescription(
        key="hard_off",
        translation_key="hard_off",
        icon="mdi:power-off",
        press_fn=_hard_off,
    ),
    IntelAmtButtonDescription(
        key="soft_off",
        translation_key="soft_off",
        icon="mdi:power-standby",
        press_fn=_soft_off,
    ),
    IntelAmtButtonDescription(
        key="hard_reset",
        translation_key="hard_reset",
        icon="mdi:restart-alert",
        press_fn=_hard_reset,
    ),
    IntelAmtButtonDescription(
        key="soft_reset",
        translation_key="soft_reset",
        icon="mdi:restart",
        press_fn=_soft_reset,
    ),
    IntelAmtButtonDescription(
        key="reboot",
        translation_key="reboot",
        icon="mdi:restart",
        press_fn=_reboot,
    ),
    IntelAmtButtonDescription(
        key="pxe_boot",
        translation_key="pxe_boot",
        icon="mdi:lan-connect",
        press_fn=_pxe_boot,
    ),
    IntelAmtButtonDescription(
        key="refresh",
        translation_key="refresh",
        icon="mdi:refresh",
        press_fn=_refresh,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Intel AMT buttons."""
    coordinator: IntelAmtCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IntelAmtButton(coordinator, description) for description in BUTTONS
    )
    alarm_manager = IntelAmtWakeAlarmButtonManager(coordinator, async_add_entities)
    entry.async_on_unload(coordinator.async_add_listener(alarm_manager.async_update))
    alarm_manager.async_update()


class IntelAmtButton(IntelAmtEntity, ButtonEntity):
    """Intel AMT action button."""

    def __init__(
        self,
        coordinator: IntelAmtCoordinator,
        description: IntelAmtButtonDescription,
    ) -> None:
        super().__init__(coordinator)
        self._description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_translation_key = description.translation_key
        self._attr_icon = description.icon

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._description.press_fn(self.coordinator)


class IntelAmtDeleteWakeAlarmButton(IntelAmtEntity, ButtonEntity):
    """Delete a single scheduled wake alarm."""

    _attr_icon = "mdi:alarm-off"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: IntelAmtCoordinator, alarm: AmtAlarm) -> None:
        super().__init__(coordinator)
        self._instance_id = alarm.instance_id
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_delete_wake_{alarm.instance_id}"
        )
        label = alarm.element_name or alarm.instance_id
        if alarm.start_time is not None:
            self._attr_name = f"Delete wake: {label}"
        else:
            self._attr_name = f"Delete wake: {label}"

    async def async_press(self) -> None:
        """Delete this wake alarm."""
        await self.coordinator.async_delete_wake_alarm(self._instance_id)


class IntelAmtWakeAlarmButtonManager:
    """Create and remove delete buttons as alarms change."""

    def __init__(
        self,
        coordinator: IntelAmtCoordinator,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.coordinator = coordinator
        self._async_add_entities = async_add_entities
        self._entities: dict[str, IntelAmtDeleteWakeAlarmButton] = {}

    @callback
    def async_update(self) -> None:
        """Sync delete buttons with coordinator alarm list."""
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            return

        alarms = {
            alarm.instance_id: alarm for alarm in self.coordinator.data.wake_alarms
        }

        for instance_id in list(self._entities):
            if instance_id not in alarms:
                entity = self._entities.pop(instance_id)
                entity.hass.async_create_task(entity.async_remove())

        to_add: list[IntelAmtDeleteWakeAlarmButton] = []
        for instance_id, alarm in alarms.items():
            if instance_id not in self._entities:
                entity = IntelAmtDeleteWakeAlarmButton(self.coordinator, alarm)
                self._entities[instance_id] = entity
                to_add.append(entity)

        if to_add:
            self._async_add_entities(to_add)
