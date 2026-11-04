"""Constants for the RD4 Afvalkalender integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Final

DOMAIN: Final = "rd4_afval"
LOGGER = logging.getLogger(__package__)

CONF_POSTCODE: Final = "postcode"
CONF_HOUSE_NUMBER: Final = "house_number"
CONF_EXTENSION: Final = "house_number_extension"

# Unofficial API used by https://mijn.rd4.nl/kalender (no authentication).
API_BASE: Final = "https://data.rd4.nl/api/v1"
REQUEST_TIMEOUT: Final = 20
USER_AGENT: Final = "HomeAssistant-rd4_afval (+https://github.com/dash82/rd4_hacs)"

# The calendar only changes a few times a year; be polite to the API.
UPDATE_INTERVAL: Final = timedelta(hours=12)
RETRY_INTERVAL: Final = 15 * 60  # seconds, after a failed update

# Waste types known to the RD4 API. Unknown types are still exposed with a
# generic name, so new types appearing upstream do not break the integration.
KNOWN_WASTE_TYPES: Final = (
    "residual_waste",
    "gft",
    "paper",
    "pruning_waste",
    "pmd",
    "best_bag",
    "christmas_trees",
    "textile",
)

# Collected only after the resident books a pickup. Shown in the calendar and
# as their own sensor, but left out of the "next pickup" summary so reminders
# don't fire for a collection nobody ordered.
APPOINTMENT_TYPES: Final = frozenset({"pruning_waste"})

# Names used for calendar events and the "next pickup types" sensor. Entity
# names come from translations/*.json; these mirror them for use in states.
WASTE_NAMES: Final[dict[str, dict[str, str]]] = {
    "en": {
        "residual_waste": "Residual waste",
        "gft": "Organic waste (GFT)",
        "paper": "Paper",
        "pruning_waste": "Pruning waste (by appointment)",
        "pmd": "Plastic, metal & drink cartons (PMD)",
        "best_bag": "BEST bag",
        "christmas_trees": "Christmas trees",
        "textile": "Textile",
    },
    "nl": {
        "residual_waste": "Restafval",
        "gft": "GFT en etensresten",
        "paper": "Papierafval",
        "pruning_waste": "Snoeiafval op afspraak",
        "pmd": "PMD-verpakkingen",
        "best_bag": "BEST-tas",
        "christmas_trees": "Kerstbomen",
        "textile": "Textiel",
    },
}


def waste_name(language: str, waste_type: str) -> str:
    """Return a human readable name for a waste type in the given language."""
    names = WASTE_NAMES["nl" if language.lower().startswith("nl") else "en"]
    return names.get(waste_type, waste_type.replace("_", " ").capitalize())
