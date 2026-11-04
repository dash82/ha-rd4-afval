"""Base entity for the RD4 Afvalkalender integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_EXTENSION, CONF_HOUSE_NUMBER, CONF_POSTCODE, DOMAIN
from .coordinator import Rd4Coordinator


class Rd4Entity(CoordinatorEntity[Rd4Coordinator]):
    """Base class: one device per configured address."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Rd4Coordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        address = (
            f"{entry.data[CONF_POSTCODE]} {entry.data[CONF_HOUSE_NUMBER]}"
            f"{entry.data.get(CONF_EXTENSION) or ''}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"RD4 {address}",
            manufacturer="RD4",
            model="Waste calendar",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://mijn.rd4.nl/kalender",
        )
