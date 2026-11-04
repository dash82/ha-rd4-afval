"""Calendar platform for the RD4 Afvalkalender integration."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import Pickup
from .const import waste_name
from .coordinator import Rd4ConfigEntry, Rd4Coordinator
from .entity import Rd4Entity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Rd4ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar."""
    async_add_entities([Rd4Calendar(entry.runtime_data)])


class Rd4Calendar(Rd4Entity, CalendarEntity):
    """All pickups as all-day events."""

    _attr_translation_key = "calendar"

    def __init__(self, coordinator: Rd4Coordinator) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_calendar"

    def _to_event(self, pickup: Pickup) -> CalendarEvent:
        return CalendarEvent(
            start=pickup.day,
            end=pickup.day + timedelta(days=1),
            summary=waste_name(self.hass.config.language, pickup.waste_type),
            uid=f"{pickup.waste_type}-{pickup.day.isoformat()}",
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next (or current) pickup."""
        upcoming = self.coordinator.data.upcoming(dt_util.now().date())
        return self._to_event(upcoming[0]) if upcoming else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return pickups between start_date (inclusive) and end_date (exclusive)."""
        start = dt_util.as_local(start_date).date()
        end = dt_util.as_local(end_date).date()
        return [
            self._to_event(pickup)
            for pickup in self.coordinator.data.pickups
            if start <= pickup.day < end
        ]
