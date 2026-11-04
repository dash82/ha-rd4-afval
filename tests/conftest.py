"""Shared fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rd4_afval.const import (
    API_BASE,
    CONF_EXTENSION,
    CONF_HOUSE_NUMBER,
    CONF_POSTCODE,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"

CALENDAR_URL = f"{API_BASE}/waste-calendar"
EXTENSIONS_URL = f"{API_BASE}/addresses/extensions"
ADDRESS = "postal_code=1234+AB&house_number=1"

NOT_PUBLISHED = {
    "success": False,
    "code": 0,
    "message": "Er is geen kalender gevonden voor dit jaartal.",
    "data": [],
}
UNKNOWN_ADDRESS = {
    "success": False,
    "code": 0,
    "message": "We kunnen geen adres vinden voor de ingevulde gegevens.",
    "data": [],
}
BAD_POSTCODE = {
    "success": False,
    "code": 0,
    "message": "Ongeldige validatie.",
    "data": {"errors": {"postal_code": ["Postcode is niet geldig"]}},
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom_components in every test."""


@pytest.fixture
def calendar_2026() -> dict:
    """Trimmed copy of a real RD4 response."""
    return json.loads((Path(__file__).parent / "fixtures" / "calendar_2026.json").read_text())


@pytest.fixture
def mock_api(aioclient_mock, calendar_2026):
    """Mock a working address; 2027 is not published yet, like the real API."""
    aioclient_mock.get(
        f"{CALENDAR_URL}?{ADDRESS}&house_number_extension=A&year=2026",
        json=calendar_2026,
    )
    aioclient_mock.get(
        f"{CALENDAR_URL}?{ADDRESS}&house_number_extension=A&year=2027",
        json=NOT_PUBLISHED,
        status=422,
    )
    aioclient_mock.get(
        f"{EXTENSIONS_URL}?{ADDRESS}",
        json={"success": True, "code": 0, "message": "", "data": [None, "A", "B"]},
    )
    return aioclient_mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry for the test address."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="1234 AB 1A",
        unique_id="1234AB_1_A",
        data={CONF_POSTCODE: "1234 AB", CONF_HOUSE_NUMBER: 1, CONF_EXTENSION: "A"},
    )
