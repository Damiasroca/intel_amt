"""Binary sensor platform for Intel AMT."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IntelAmtCoordinator
from .entity import IntelAmtEntity


@dataclass(frozen=True, kw_only=True)
class IntelAmtBinarySensorDescription:
    """Describes an Intel AMT binary sensor."""

    key: str
    translation_key: str
    icon: str
    device_class: BinarySensorDeviceClass | None = None
    entity_category: EntityCategory | None = None
    is_on_fn: Callable[[IntelAmtCoordinator], bool | None]
    attributes_fn: Callable[[IntelAmtCoordinator], dict] | None = None


def _kvm_is_on(coordinator: IntelAmtCoordinator) -> bool | None:
    if not coordinator.last_update_success or coordinator.data is None:
        return None
    return coordinator.data.kvm_session_active


def _kvm_attrs(coordinator: IntelAmtCoordinator) -> dict:
    if coordinator.data is None:
        return {}
    return {"kvm_state": coordinator.data.kvm_state}


def _redirection_is_on(coordinator: IntelAmtCoordinator) -> bool | None:
    if not coordinator.last_update_success or coordinator.data is None:
        return None
    sol = coordinator.data.sol_enabled
    ider = coordinator.data.ider_enabled
    if sol is None and ider is None:
        return None
    return bool(sol) or bool(ider)


def _redirection_attrs(coordinator: IntelAmtCoordinator) -> dict:
    if coordinator.data is None:
        return {}
    return {
        "redirection_state": coordinator.data.redirection_state,
        "sol_enabled": coordinator.data.sol_enabled,
        "ider_enabled": coordinator.data.ider_enabled,
    }


BINARY_SENSORS: tuple[IntelAmtBinarySensorDescription, ...] = (
    IntelAmtBinarySensorDescription(
        key="kvm_active",
        translation_key="kvm_active",
        icon="mdi:monitor-eye",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=_kvm_is_on,
        attributes_fn=_kvm_attrs,
    ),
    IntelAmtBinarySensorDescription(
        key="redirection_enabled",
        translation_key="redirection_enabled",
        icon="mdi:lan-connect",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_redirection_is_on,
        attributes_fn=_redirection_attrs,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Intel AMT binary sensors."""
    coordinator: IntelAmtCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IntelAmtBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class IntelAmtBinarySensor(IntelAmtEntity, BinarySensorEntity):
    """Intel AMT binary sensor."""

    def __init__(
        self,
        coordinator: IntelAmtCoordinator,
        description: IntelAmtBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self._description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_translation_key = description.translation_key
        self._attr_icon = description.icon
        if description.device_class is not None:
            self._attr_device_class = description.device_class
        if description.entity_category is not None:
            self._attr_entity_category = description.entity_category

    @property
    def is_on(self) -> bool | None:
        """Return the current on/off state."""
        return self._description.is_on_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional context attributes."""
        if self._description.attributes_fn is None:
            return {}
        return self._description.attributes_fn(self.coordinator)

    @property
    def available(self) -> bool:
        """Available when the underlying value is known."""
        return self._description.is_on_fn(self.coordinator) is not None
