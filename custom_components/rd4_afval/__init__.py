"""The RD4 Afvalkalender integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change

from .api import Rd4Client
from .const import CONF_EXTENSION, CONF_HOUSE_NUMBER, CONF_POSTCODE
from .coordinator import Rd4ConfigEntry, Rd4Coordinator

PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: Rd4ConfigEntry) -> bool:
    """Set up RD4 Afvalkalender from a config entry."""
    client = Rd4Client(
        async_get_clientsession(hass),
        entry.data[CONF_POSTCODE],
        entry.data[CONF_HOUSE_NUMBER],
        entry.data.get(CONF_EXTENSION),
    )
    coordinator = Rd4Coordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # "Next pickup" states depend on today's date: refresh them at midnight
    # without hitting the API again.
    @callback
    def _midnight(_now) -> None:
        coordinator.async_update_listeners()

    entry.async_on_unload(async_track_time_change(hass, _midnight, hour=0, minute=0, second=5))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Rd4ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
