"""Allows querying the Frontier Companion API"""

import base64
import logging
from typing import Any

from aiohttp import ClientSession

from common import Good
from settings import CAPI

_TIMEOUT = 60
_URL = "https://companion.orerve.net"

_LOGGER = logging.getLogger(__name__)


class EpicFail(Exception):
    """Raised when Epic fails to authenticate CAPI."""


async def _request(url: str, headers: dict[str, str]) -> dict[str, Any]:
    data: dict[str, str | int] = {}

    async with (
        ClientSession() as session,
        session.get(url, headers=headers, timeout=_TIMEOUT) as response,
    ):
        if "purchase Elite: Dangerous" in await response.text():
            raise EpicFail

        response.raise_for_status()

        if response.content_type == "application/json":
            data = await response.json()

    return data


async def fleetcarrier(
    access_token: str,
) -> tuple[tuple[str, str, int], list[Good], str] | None:
    """
    Query the /fleetcarrier endpoint.
    Returns the (callsign, name, market_id), market contents and system.
    Returns none if the player does not own a carrier.
    """

    headers = {
        "User-Agent": CAPI.user_agent,
        "Authorization": f"Bearer {access_token}",
    }

    response = await _request(f"{_URL}/fleetcarrier", headers)
    if not response:
        return None

    market = [
        Good(
            commodity["name"],
            {
                "price": commodity["buyPrice"],
                "quantity": commodity["stock"],
                "bracket": commodity["stockBracket"],
            },
            {
                "price": commodity["sellPrice"],
                "quantity": commodity["demand"],
                "bracket": commodity["demandBracket"],
            },
            commodity["meanPrice"],
        )
        for commodity in response["market"]["commodities"]
        if commodity["categoryname"] != "NonMarketable"
    ]

    display_name = base64.b16decode(
        response["name"]["vanityName"], casefold=True
    ).decode("utf-8")

    _LOGGER.info(
        "'[%s] %s' is selling %s items in '%s'",
        response["name"]["callsign"],
        display_name,
        len(market),
        response["currentStarSystem"],
    )

    return (
        (response["name"]["callsign"], display_name, response["market"]["id"]),
        market,
        response["currentStarSystem"],
    )


async def profile(access_token: str) -> str:
    """
    Query the /profile endpoint
    Returns the commander name
    """

    headers = {
        "User-Agent": CAPI.user_agent,
        "Authorization": f"Bearer {access_token}",
    }
    response = await _request(f"{_URL}/profile", headers)

    _LOGGER.info("Fetched commander profile for '%s'", response["commander"]["name"])

    return response["commander"]["name"]
