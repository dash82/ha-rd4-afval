"""Sensors for the RD4 Afvalkalender integration."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import KNOWN_WASTE_TYPES, waste_name
from .coordinator import Rd4ConfigEntry, Rd4Coordinator
from .entity import Rd4Entity

PARALLEL_UPDATES = 0

UPCOMING_ATTRIBUTE_COUNT = 5


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Rd4ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors, adding new waste types as RD4 introduces them."""
    coordinator = entry.runtime_data
    async_add_entities([NextPickupSensor(coordinator), NextPickupTypesSensor(coordinator)])

    known: set[str] = set()

    @callback
    def _add_new_types() -> None:
        new = coordinator.data.waste_types - known
        if not new:
            return
        known.update(new)
        async_add_entities(WasteTypeSensor(coordinator, t) for t in sorted(new))

    _add_new_types()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_types))


def _today() -> date:
    return dt_util.now().date()


class WasteTypeSensor(Rd4Entity, SensorEntity):
    """Date of the next pickup of one waste type."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: Rd4Coordinator, waste_type: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._waste_type = waste_type
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{waste_type}"
        if waste_type in KNOWN_WASTE_TYPES:
            self._attr_translation_key = waste_type
        else:
            self._attr_translation_key = "other_waste"
            self._attr_translation_placeholders = {
                "waste_type": waste_type.replace("_", " ").capitalize()
            }

    def _upcoming(self) -> list[date]:
        return [pickup.day for pickup in self.coordinator.data.upcoming(_today(), self._waste_type)]

    @property
    def native_value(self) -> date | None:
        """Return the next pickup date."""
        upcoming = self._upcoming()
        return upcoming[0] if upcoming else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return days until the pickup and the dates after it."""
        upcoming = self._upcoming()
        return {
            "days_until": (upcoming[0] - _today()).days if upcoming else None,
            "upcoming": [d.isoformat() for d in upcoming[:UPCOMING_ATTRIBUTE_COUNT]],
        }


class NextPickupSensor(Rd4Entity, SensorEntity):
    """Date of the next scheduled collection day (appointments excluded)."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_translation_key = "next_pickup"

    def __init__(self, coordinator: Rd4Coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_next_pickup"

    @property
    def native_value(self) -> date | None:
        """Return the date of the next collection day."""
        pickups = self.coordinator.data.next_scheduled(_today())
        return pickups[0].day if pickups else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the waste types collected that day."""
        pickups = self.coordinator.data.next_scheduled(_today())
        language = self.hass.config.language
        return {
            "days_until": (pickups[0].day - _today()).days if pickups else None,
            "waste_types": [p.waste_type for p in pickups],
            "waste_type_names": [waste_name(language, p.waste_type) for p in pickups],
        }


class NextPickupTypesSensor(Rd4Entity, SensorEntity):
    """Readable list of what is collected on the next collection day."""

    _attr_translation_key = "next_pickup_types"

    def __init__(self, coordinator: Rd4Coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_next_pickup_types"

    @property
    def native_value(self) -> str | None:
        """Return e.g. "GFT en etensresten, PMD-verpakkingen"."""
        pickups = self.coordinator.data.next_scheduled(_today())
        if not pickups:
            return None
        language = self.hass.config.language
        return ", ".join(waste_name(language, p.waste_type) for p in pickups)
