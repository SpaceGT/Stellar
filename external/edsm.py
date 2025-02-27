"""Allows pulling data from the EDSM system API"""

from datetime import datetime, timezone
from typing import Any

from aiohttp import ClientSession

from common import Good, System
from settings import SOFTWARE
from utils.points import Point3D

_TIMEOUT = 60
_STATION_URL = "https://www.edsm.net/api-system-v1/stations"
_SYSTEM_URL = "https://www.edsm.net/api-v1/system"


async def _request(url: str) -> dict[str, Any]:
    headers = {"User-Agent": SOFTWARE.user_agent}

    async with (
        ClientSession(raise_for_status=True) as session,
        session.get(url, headers=headers, timeout=_TIMEOUT) as response,
    ):
        data: dict[str, Any] = await response.json()

    return data


async def _market(market_id: int) -> dict[str, Any]:
    return await _request(f"{_STATION_URL}/market?marketId={market_id}")


async def _system(system_id: int) -> dict[str, Any]:
    return await _request(f"{_STATION_URL}?systemId={system_id}")


async def system(name: str) -> System | None:
    """Get core system info by name and verify it exists."""
    response = await _request(f"{_SYSTEM_URL}?systemName={name}&showCoordinates=1")

    if not response:
        return None

    return System(
        response["name"],
        Point3D(
            response["coords"]["x"],
            response["coords"]["y"],
            response["coords"]["z"],
        ),
    )


async def market(market_id: int) -> list[Good]:
    """Get the market of a station."""

    market_response = await _market(market_id)

    if market_response["commodities"] is None:
        return []

    market_ = [
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
            },
        )
        for commodity in market_response["commodities"]
    ]

    return market_


async def overview(
    market_id: int, timestamp: bool = False
) -> tuple[list[Good], System, datetime | None]:
    """Get the market, system and (optional) update time of a station."""

    market_response = await _market(market_id)

    if market_response["commodities"] is None:
        market_ = []

    else:
        market_ = [
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
                },
            )
            for commodity in market_response["commodities"]
        ]

    if not timestamp:
        return market_, market_response["name"], None

    system_response = await _system(market_response["id"])

    update = next(
        (
            datetime.strptime(
                station["updateTime"]["market"], "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=timezone.utc)
            for station in system_response["stations"]
            if station["marketId"] == market_id
            and station["updateTime"]["market"] is not None
        ),
        None,
    )

    system_info = await system(market_response["name"])
    assert system_info

    return market_, system_info, update


async def market_id(callsign: str, system: str) -> int | None:
    """Return the Market ID of a carrier."""
    id_response = await _request(f"{_SYSTEM_URL}?systemName={system}&showId=1")
    if not id_response:
        return None

    system_response = await _system(id_response["id"])
    for station in system_response["stations"]:
        if station["name"] == callsign:
            return station["marketId"]

    return None
