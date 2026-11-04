"""Tests for the API client."""

from __future__ import annotations

from datetime import date

import aiohttp
import pytest

from custom_components.rd4_afval.api import (
    Pickup,
    Rd4AddressNotFoundError,
    Rd4CalendarNotPublishedError,
    Rd4Client,
    Rd4ConnectionError,
    Rd4InvalidInputError,
    normalize_postcode,
)

from .conftest import (
    ADDRESS,
    BAD_POSTCODE,
    CALENDAR_URL,
    EXTENSIONS_URL,
    NOT_PUBLISHED,
    UNKNOWN_ADDRESS,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1234AB", "1234 AB"), (" 1234 ab ", "1234 AB"), ("1234  AB", "1234 AB")],
)
def test_normalize_postcode(raw: str, expected: str) -> None:
    assert normalize_postcode(raw) == expected


@pytest.mark.parametrize("raw", ["", "12345", "ABCD12", "1234 A"])
def test_normalize_postcode_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_postcode(raw)


async def test_get_calendar(hass, mock_api) -> None:
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    client = Rd4Client(async_get_clientsession(hass), "1234AB", 1, "A")
    pickups = await client.async_get_calendar(2026)

    assert pickups == sorted(pickups)
    assert Pickup(date(2026, 11, 5), "gft") in pickups
    assert Pickup(date(2026, 11, 12), "residual_waste") in pickups
    assert {p.waste_type for p in pickups} == {
        "paper",
        "best_bag",
        "pruning_waste",
        "gft",
        "pmd",
        "residual_waste",
    }


async def test_get_extensions_drops_null(hass, mock_api) -> None:
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    client = Rd4Client(async_get_clientsession(hass), "1234 AB", 1)
    assert await client.async_get_extensions() == ["A", "B"]


@pytest.mark.parametrize(
    ("status", "payload", "error"),
    [
        (422, NOT_PUBLISHED, Rd4CalendarNotPublishedError),
        (422, UNKNOWN_ADDRESS, Rd4AddressNotFoundError),
        (422, BAD_POSTCODE, Rd4InvalidInputError),
        (500, {"message": "boom"}, Rd4ConnectionError),
        (200, ["not", "a", "dict"], Rd4ConnectionError),
    ],
)
async def test_error_mapping(hass, aioclient_mock, status, payload, error) -> None:
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    aioclient_mock.get(f"{CALENDAR_URL}?{ADDRESS}", json=payload, status=status)
    client = Rd4Client(async_get_clientsession(hass), "1234 AB", 1)
    with pytest.raises(error):
        await client.async_get_calendar(2026)


@pytest.mark.parametrize("exc", [TimeoutError, aiohttp.ClientError])
async def test_network_errors(hass, aioclient_mock, exc) -> None:
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    aioclient_mock.get(EXTENSIONS_URL, exc=exc)
    client = Rd4Client(async_get_clientsession(hass), "1234 AB", 1)
    with pytest.raises(Rd4ConnectionError):
        await client.async_get_extensions()


async def test_malformed_items_are_skipped(hass, aioclient_mock) -> None:
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    aioclient_mock.get(
        f"{CALENDAR_URL}?{ADDRESS}",
        json={
            "success": True,
            "data": {
                "items": [
                    [
                        {"date": "nope", "type": "gft"},
                        {"type": "pmd"},
                        {"date": "2026-01-02", "type": "paper"},
                    ]
                ]
            },
        },
    )
    client = Rd4Client(async_get_clientsession(hass), "1234 AB", 1)
    assert await client.async_get_calendar(2026) == [Pickup(date(2026, 1, 2), "paper")]
