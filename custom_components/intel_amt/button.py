"""Button platform for Intel AMT."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
