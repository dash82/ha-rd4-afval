"""Client for the (unofficial) RD4 waste calendar API."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import aiohttp

from .const import API_BASE, REQUEST_TIMEOUT, USER_AGENT

_POSTCODE_RE = re.compile(r"^(\d{4})\s*([A-Za-z]{2})$")


class Rd4Error(Exception):
    """Base error for the RD4 API."""


class Rd4ConnectionError(Rd4Error):
    """The API could not be reached or returned an unusable response."""


class Rd4InvalidInputError(Rd4Error):
    """The API rejected the postcode or house number format."""


class Rd4AddressNotFoundError(Rd4Error):
    """RD4 has no address for the given details."""


class Rd4CalendarNotPublishedError(Rd4Error):
    """RD4 has not published a calendar for the requested year (yet)."""


@dataclass(frozen=True, order=True, slots=True)
class Pickup:
    """A single collection of one waste type on one day."""

    day: date
    waste_type: str


def normalize_postcode(value: str) -> str:
    """Return a Dutch postcode as ``1234 AB`` or raise ValueError."""
    match = _POSTCODE_RE.match(value.strip())
    if not match:
        raise ValueError(f"Invalid postcode: {value!r}")
    return f"{match[1]} {match[2].upper()}"


def _parse_pickups(data: Any) -> list[Pickup]:
    """Parse the ``data`` member of a waste-calendar response."""
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise Rd4ConnectionError("Unexpected calendar response")

    pickups: list[Pickup] = []
    # The API wraps the list in another list; flatten defensively.
    stack = list(items)
    while stack:
        item = stack.pop(0)
        if isinstance(item, list):
            stack = [*item, *stack]
            continue
        try:
            pickups.append(Pickup(date.fromisoformat(item["date"]), str(item["type"])))
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed entries instead of failing the update
    return sorted(set(pickups))


class Rd4Client:
    """Small async client around data.rd4.nl."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        postcode: str,
        house_number: int,
        extension: str | None = None,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._params: dict[str, str] = {
            "postal_code": normalize_postcode(postcode),
            "house_number": str(house_number),
        }
        self._extension = extension or None

    async def _request(self, path: str, params: dict[str, str]) -> Any:
        """Do a GET request and return the ``data`` member of the payload."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(
                    f"{API_BASE}/{path}",
                    params=params,
                    headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                ) as response:
                    status = response.status
                    payload = await response.json(content_type=None)
        except TimeoutError as err:
            raise Rd4ConnectionError("Timeout talking to RD4") from err
        except (aiohttp.ClientError, ValueError) as err:
            raise Rd4ConnectionError(f"Error talking to RD4: {err}") from err

        if status >= 500 or not isinstance(payload, dict):
            raise Rd4ConnectionError(f"RD4 returned an unusable response ({status})")

        if status < 400 and payload.get("success"):
            return payload.get("data")

        message = str(payload.get("message") or "")
        data = payload.get("data")
        if isinstance(data, dict) and data.get("errors"):
            raise Rd4InvalidInputError(message or str(data["errors"]))
        # The API only distinguishes these cases through its (Dutch) message.
        lowered = message.lower()
        if "jaartal" in lowered:
            raise Rd4CalendarNotPublishedError(message)
        if "adres" in lowered:
            raise Rd4AddressNotFoundError(message)
        raise Rd4Error(message or f"RD4 returned HTTP {status}")

    async def async_get_extensions(self) -> list[str]:
        """Return the house number extensions that exist for this address."""
        data = await self._request("addresses/extensions", self._params)
        if not isinstance(data, list):
            return []
        return [str(ext) for ext in data if ext]

    async def async_get_calendar(self, year: int) -> list[Pickup]:
        """Return all pickups of a year."""
        params = {**self._params, "year": str(year)}
        if self._extension:
            params["house_number_extension"] = self._extension
        return _parse_pickups(await self._request("waste-calendar", params))
