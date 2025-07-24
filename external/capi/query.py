"""Allows querying the Frontier Companion API"""

import base64
import logging
from enum import StrEnum
from typing import Any

from aiohttp import ClientSession

from common import Good
from common.depots import stock_bracket
from settings import CAPI

_TIMEOUT = 60
_URL = "https://companion.orerve.net"

_LOGGER = logging.getLogger(__name__)


class TokenFail(Exception):
    """Raised when using invalid or expired tokens."""


class EpicFail(Exception):
    """Raised when Epic fails to authenticate CAPI."""


class CapiFail(Exception):
    """Rasied when cAPI is down for maintenance."""


class Endpoint(StrEnum):
    FLEET_CARRIER = "fleetcarrier"
    PROFILE = "profile"
    SHIPYARD = "shipyard"
    MARKET = "market"
    JOURNAL = "journal"
    COMMUNITY_GOALS = "communitygoals"


async def _request(endpoint: Endpoint, headers: dict[str, str]) -> dict[str, Any]:
    data: dict[str, str | int] = {}

    async with (
        ClientSession() as session,
        session.get(
            f"{_URL}/{endpoint}", headers=headers, timeout=_TIMEOUT
        ) as response,
    ):
        if "purchase Elite: Dangerous" in await response.text():
            raise EpicFail

        # Capi lacks consistent status codes (search 418)
        if response.status in (418, 500, 502, 503, 504):
            raise CapiFail

        if response.status == 401:
            raise TokenFail

        response.raise_for_status()

        if response.content_type == "application/json":
            data = await response.json()

    return data


async def request(endpoint: Endpoint, access_token: str) -> dict[str, Any]:
    """Query a given endpoint and return raw JSON."""

    headers = {
        "User-Agent": CAPI.user_agent,
        "Authorization": f"Bearer {access_token}",
    }
    return await _request(endpoint, headers)


async def fleetcarrier(
    access_token: str,
) -> tuple[tuple[str, str, int], list[Good], str] | None:
    """
    Query the /fleetcarrier endpoint.
    Returns the (callsign, name, market_id), market contents and system.
    Returns none if the player does not own a carrier.
    """

    response = await request(Endpoint.FLEET_CARRIER, access_token)
    if not response:
        return None

    market: list[Good] = []
    orders = response["orders"]["commodities"]

    for sell_order in orders["sales"]:
        market.append(Good(
            name=sell_order["name"],
            stock_info={
                "price": int(sell_order["price"]),
                "quantity": int(sell_order["stock"]),
                "bracket": stock_bracket(int(sell_order["stock"])),
            },
            demand_info={}
        ))

    for buy_order in orders["purchases"]:
        market.append(Good(
            name=buy_order["name"],
            demand_info={
                "price": buy_order["price"],
                "quantity": buy_order["outstanding"],
                "bracket": stock_bracket(buy_order["outstanding"]),
            },
            stock_info={}
        ))

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
    response = await request(Endpoint.PROFILE, access_token)
    _LOGGER.info("Fetched commander profile for '%s'", response["commander"]["name"])

    return response["commander"]["name"]
