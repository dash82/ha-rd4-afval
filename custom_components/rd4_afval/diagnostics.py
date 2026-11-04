"""Diagnostics support for the RD4 Afvalkalender integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_EXTENSION, CONF_HOUSE_NUMBER, CONF_POSTCODE
from .coordinator import Rd4ConfigEntry

TO_REDACT = {CONF_POSTCODE, CONF_HOUSE_NUMBER, CONF_EXTENSION, "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: Rd4ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.data
    return {
        "entry": async_redact_data({"title": entry.title, **entry.data}, TO_REDACT),
        "waste_types": sorted(data.waste_types),
        "pickup_count": len(data.pickups),
        "first_pickup": data.pickups[0].day.isoformat() if data.pickups else None,
        "last_pickup": data.pickups[-1].day.isoformat() if data.pickups else None,
    }
