"""Config flow for the RD4 Afvalkalender integration."""

from __future__ import annotations

import contextlib
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)
from homeassistant.util import dt as dt_util

from .api import (
    Rd4AddressNotFoundError,
    Rd4CalendarNotPublishedError,
    Rd4Client,
    Rd4ConnectionError,
    Rd4Error,
    Rd4InvalidInputError,
    normalize_postcode,
)
from .const import CONF_EXTENSION, CONF_HOUSE_NUMBER, CONF_POSTCODE, DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_POSTCODE): TextSelector(),
        vol.Required(CONF_HOUSE_NUMBER): NumberSelector(
            NumberSelectorConfig(min=1, max=99999, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_EXTENSION): TextSelector(),
    }
)


def _unique_id(data: dict[str, Any]) -> str:
    postcode = data[CONF_POSTCODE].replace(" ", "")
    return f"{postcode}_{data[CONF_HOUSE_NUMBER]}_{data.get(CONF_EXTENSION, '')}".upper()


class Rd4ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RD4 Afvalkalender."""

    VERSION = 1

    async def _async_validate(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, dict[str, str], dict[str, str]]:
        """Check the address against RD4.

        Returns the config entry data (or None), form errors and placeholders.
        """
        errors: dict[str, str] = {}
        placeholders = {"extensions": "-"}

        try:
            postcode = normalize_postcode(user_input[CONF_POSTCODE])
        except ValueError:
            errors[CONF_POSTCODE] = "invalid_postcode"
            return None, errors, placeholders

        number = int(user_input[CONF_HOUSE_NUMBER])
        extension = (user_input.get(CONF_EXTENSION) or "").strip()
        client = Rd4Client(async_get_clientsession(self.hass), postcode, number, extension or None)

        try:
            await client.async_get_calendar(dt_util.now().year)
        except Rd4InvalidInputError:
            errors[CONF_POSTCODE] = "invalid_postcode"
        except Rd4AddressNotFoundError:
            errors["base"] = "address_not_found"
            with contextlib.suppress(Rd4Error):
                placeholders["extensions"] = ", ".join(await client.async_get_extensions()) or "-"
        except Rd4CalendarNotPublishedError:
            errors["base"] = "no_calendar"
        except Rd4ConnectionError:
            errors["base"] = "cannot_connect"
        except Rd4Error:
            LOGGER.exception("Unexpected error validating address")
            errors["base"] = "unknown"

        if errors:
            return None, errors, placeholders

        data: dict[str, Any] = {CONF_POSTCODE: postcode, CONF_HOUSE_NUMBER: number}
        if extension:
            data[CONF_EXTENSION] = extension
        return data, errors, placeholders

    @staticmethod
    def _title(data: dict[str, Any]) -> str:
        return f"{data[CONF_POSTCODE]} {data[CONF_HOUSE_NUMBER]}{data.get(CONF_EXTENSION, '')}"

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders = {"extensions": "-"}
        if user_input is not None:
            data, errors, placeholders = await self._async_validate(user_input)
            if data is not None:
                await self.async_set_unique_id(_unique_id(data))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=self._title(data), data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA, user_input),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user move the entry to another address."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        placeholders = {"extensions": "-"}
        if user_input is not None:
            data, errors, placeholders = await self._async_validate(user_input)
            if data is not None:
                unique_id = _unique_id(data)
                if any(
                    other.unique_id == unique_id and other.entry_id != entry.entry_id
                    for other in self._async_current_entries()
                ):
                    return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    entry, unique_id=unique_id, title=self._title(data), data=data
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA, user_input or entry.data),
            errors=errors,
            description_placeholders=placeholders,
        )
