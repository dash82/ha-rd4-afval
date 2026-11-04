"""Tests for setup, sensors, calendar and diagnostics."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.rd4_afval.const import DOMAIN
from custom_components.rd4_afval.diagnostics import async_get_config_entry_diagnostics

from .conftest import ADDRESS, CALENDAR_URL

TODAY = "2026-11-04 10:00:00+01:00"  # a Wednesday: BEST bag + pruning waste day


async def _setup(hass: HomeAssistant, entry) -> None:
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _entity_id(hass: HomeAssistant, entry, suffix: str) -> str:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor" if suffix != "calendar" else "calendar",
        DOMAIN,
        f"{entry.entry_id}_{suffix}",
    )
    assert entity_id, suffix
    return entity_id


async def test_sensors(hass, mock_api, config_entry, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(TODAY)
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(_entity_id(hass, config_entry, "gft"))
    assert state.state == "2026-11-05"
    assert state.attributes["days_until"] == 1
    assert state.attributes["upcoming"][:2] == ["2026-11-05", "2026-11-19"]

    assert hass.states.get(_entity_id(hass, config_entry, "residual_waste")).state == "2026-11-12"
    # Appointment-only waste still has its own sensor ...
    assert hass.states.get(_entity_id(hass, config_entry, "pruning_waste")).state == "2026-11-04"

    # ... but the summary only reports the regular schedule.
    nxt = hass.states.get(_entity_id(hass, config_entry, "next_pickup"))
    assert nxt.state == "2026-11-04"
    assert nxt.attributes["waste_types"] == ["best_bag"]
    assert nxt.attributes["days_until"] == 0
    assert hass.states.get(_entity_id(hass, config_entry, "next_pickup_types")).state == "BEST bag"


async def test_midnight_rollover_without_api_call(
    hass, mock_api, config_entry, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-04 23:59:00+01:00")
    await _setup(hass, config_entry)
    calls = mock_api.call_count
    entity_id = _entity_id(hass, config_entry, "next_pickup")
    assert hass.states.get(entity_id).state == "2026-11-04"

    freezer.move_to("2026-11-05 00:00:05+01:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "2026-11-05"
    assert state.attributes["waste_types"] == ["gft", "pmd"]
    assert mock_api.call_count == calls


async def test_calendar(hass, mock_api, config_entry, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(TODAY)
    await _setup(hass, config_entry)
    entity_id = _entity_id(hass, config_entry, "calendar")

    state = hass.states.get(entity_id)
    assert state.state == "on"
    assert state.attributes["message"] in {"BEST bag", "Pruning waste (by appointment)"}

    events = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": entity_id,
            "start_date_time": "2026-11-05 00:00:00",
            "end_date_time": "2026-11-06 00:00:00",
        },
        blocking=True,
        return_response=True,
    )
    summaries = sorted(e["summary"] for e in events[entity_id]["events"])
    assert summaries == ["Organic waste (GFT)", "Plastic, metal & drink cartons (PMD)"]


async def test_new_waste_type_gets_a_sensor(
    hass, aioclient_mock, config_entry, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(TODAY)
    aioclient_mock.get(
        f"{CALENDAR_URL}?{ADDRESS}&house_number_extension=A&year=2026",
        json={
            "success": True,
            "data": {"items": [[{"date": "2026-11-20", "type": "bulky_waste"}]]},
        },
    )
    aioclient_mock.get(
        f"{CALENDAR_URL}?{ADDRESS}&house_number_extension=A&year=2027",
        json={"success": False, "message": "Er is geen kalender gevonden voor dit jaartal."},
        status=422,
    )
    await _setup(hass, config_entry)
    state = hass.states.get(_entity_id(hass, config_entry, "bulky_waste"))
    assert state.state == "2026-11-20"
    assert state.name.endswith("Bulky waste")


async def test_setup_retries_when_api_down(hass, aioclient_mock, config_entry) -> None:
    aioclient_mock.get(CALENDAR_URL, status=503, text="down")
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload(hass, mock_api, config_entry, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(TODAY)
    await _setup(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_diagnostics_redacts_address(
    hass, mock_api, config_entry, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(TODAY)
    await _setup(hass, config_entry)
    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["entry"] == {
        "title": "**REDACTED**",
        "postcode": "**REDACTED**",
        "house_number": "**REDACTED**",
        "house_number_extension": "**REDACTED**",
    }
    assert diag["waste_types"] == [
        "best_bag",
        "gft",
        "paper",
        "pmd",
        "pruning_waste",
        "residual_waste",
    ]
