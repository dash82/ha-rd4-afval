"""DataUpdateCoordinator for the RD4 Afvalkalender integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    Pickup,
    Rd4CalendarNotPublishedError,
    Rd4Client,
    Rd4Error,
)
from .const import APPOINTMENT_TYPES, DOMAIN, LOGGER, RETRY_INTERVAL, UPDATE_INTERVAL

type Rd4ConfigEntry = ConfigEntry[Rd4Coordinator]


@dataclass(frozen=True, slots=True)
class Rd4Data:
    """Everything fetched from RD4, sorted by date."""

    pickups: tuple[Pickup, ...]

    @property
    def waste_types(self) -> set[str]:
        """Return all waste types present in the calendar."""
        return {pickup.waste_type for pickup in self.pickups}

    def upcoming(self, today: date, waste_type: str | None = None) -> list[Pickup]:
        """Return pickups from ``today`` onwards, optionally for one type."""
        return [
            pickup
            for pickup in self.pickups
            if pickup.day >= today and (waste_type is None or pickup.waste_type == waste_type)
        ]

    def next_scheduled(self, today: date) -> list[Pickup]:
        """Return the pickups of the next collection day, appointments excluded."""
        scheduled = [
            pickup for pickup in self.upcoming(today) if pickup.waste_type not in APPOINTMENT_TYPES
        ]
        if not scheduled:
            return []
        first_day = scheduled[0].day
        return [pickup for pickup in scheduled if pickup.day == first_day]


class Rd4Coordinator(DataUpdateCoordinator[Rd4Data]):
    """Fetch the waste calendar for the configured address."""

    config_entry: Rd4ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: Rd4ConfigEntry, client: Rd4Client
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> Rd4Data:
        """Fetch this year's calendar, plus next year's once RD4 publishes it."""
        year = dt_util.now().year
        try:
            pickups = await self.client.async_get_calendar(year)
        except Rd4Error as err:
            raise UpdateFailed(
                f"Error fetching calendar: {err}", retry_after=RETRY_INTERVAL
            ) from err

        try:
            pickups += await self.client.async_get_calendar(year + 1)
        except Rd4CalendarNotPublishedError:
            LOGGER.debug("No calendar published for %s yet", year + 1)
        except Rd4Error as err:
            raise UpdateFailed(
                f"Error fetching calendar: {err}", retry_after=RETRY_INTERVAL
            ) from err

        return Rd4Data(pickups=tuple(sorted(set(pickups))))
