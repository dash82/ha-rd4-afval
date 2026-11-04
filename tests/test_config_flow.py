"""Tests for the config flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rd4_afval.const import (
    CONF_EXTENSION,
    CONF_HOUSE_NUMBER,
    CONF_POSTCODE,
    DOMAIN,
)

from .conftest import ADDRESS, BAD_POSTCODE, CALENDAR_URL, EXTENSIONS_URL, UNKNOWN_ADDRESS

USER_INPUT = {CONF_POSTCODE: "1234ab", CONF_HOUSE_NUMBER: 1, CONF_EXTENSION: "A"}


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow_success(hass, mock_api) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1234 AB 1A"
    assert result["data"] == {
        CONF_POSTCODE: "1234 AB",
        CONF_HOUSE_NUMBER: 1,
        CONF_EXTENSION: "A",
    }
    assert result["result"].unique_id == "1234AB_1_A"


async def test_user_flow_without_extension(hass, aioclient_mock, calendar_2026) -> None:
    aioclient_mock.get(f"{CALENDAR_URL}?{ADDRESS}&year=2026", json=calendar_2026)
    result = await hass.config_entries.flow.async_configure(
        (await _start(hass))["flow_id"],
        {CONF_POSTCODE: "1234 AB", CONF_HOUSE_NUMBER: 1},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_EXTENSION not in result["data"]


async def test_invalid_postcode_never_hits_api(hass, aioclient_mock) -> None:
    result = await hass.config_entries.flow.async_configure(
        (await _start(hass))["flow_id"],
        {CONF_POSTCODE: "nope", CONF_HOUSE_NUMBER: 1},
    )
    assert result["errors"] == {CONF_POSTCODE: "invalid_postcode"}
    assert aioclient_mock.call_count == 0


async def test_api_rejects_postcode(hass, aioclient_mock) -> None:
    aioclient_mock.get(CALENDAR_URL, json=BAD_POSTCODE, status=422)
    result = await hass.config_entries.flow.async_configure(
        (await _start(hass))["flow_id"], USER_INPUT
    )
    assert result["errors"] == {CONF_POSTCODE: "invalid_postcode"}


async def test_unknown_address_lists_extensions(hass, aioclient_mock) -> None:
    aioclient_mock.get(CALENDAR_URL, json=UNKNOWN_ADDRESS, status=422)
    aioclient_mock.get(EXTENSIONS_URL, json={"success": True, "data": [None, "B", "C"]})
    result = await hass.config_entries.flow.async_configure(
        (await _start(hass))["flow_id"], USER_INPUT
    )
    assert result["errors"] == {"base": "address_not_found"}
    assert result["description_placeholders"] == {"extensions": "B, C"}


async def test_cannot_connect_then_recover(hass, aioclient_mock, mock_api) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(CALENDAR_URL, status=503, text="down")
    result = await hass.config_entries.flow.async_configure(
        (await _start(hass))["flow_id"], USER_INPUT
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_aborts(hass, mock_api, config_entry) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(
        (await _start(hass))["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(hass, aioclient_mock, mock_api, calendar_2026, config_entry) -> None:
    config_entry.add_to_hass(hass)
    aioclient_mock.get(
        f"{CALENDAR_URL}?postal_code=1234+AB&house_number=2&year=2026",
        json=calendar_2026,
    )
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_POSTCODE: "1234 AB", CONF_HOUSE_NUMBER: 2}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_POSTCODE: "1234 AB", CONF_HOUSE_NUMBER: 2}
    assert config_entry.unique_id == "1234AB_2_"
    assert config_entry.title == "1234 AB 2"


async def test_reconfigure_to_existing_address_aborts(hass, mock_api, config_entry) -> None:
    config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN, unique_id="1234AB_2_", data={CONF_POSTCODE: "1234 AB", CONF_HOUSE_NUMBER: 2}
    )
    other.add_to_hass(hass)
    mock_api.get(
        f"{CALENDAR_URL}?postal_code=1234+AB&house_number=2&year=2026",
        json={"success": True, "data": {"items": [[]]}},
    )
    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_POSTCODE: "1234 AB", CONF_HOUSE_NUMBER: 2}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
