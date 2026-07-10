"""Base entity for Intel AMT."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, CONF_NAME, DOMAIN
from .coordinator import IntelAmtCoordinator


class IntelAmtEntity(CoordinatorEntity[IntelAmtCoordinator]):
    """Base class for Intel AMT entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IntelAmtCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._entry_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, entry.data[CONF_HOST]),
            manufacturer="Intel",
            model="Active Management Technology",
            configuration_url=f"http://{entry.data[CONF_HOST]}:16992",
        )
