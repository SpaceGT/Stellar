"""Sends data to EDDN."""

import logging
from datetime import datetime, timezone
from typing import Any

from aiohttp import ClientSession

from common import Good
from settings import EDDN

_ENDPOINT = "https://eddn.edcd.io:4430/upload/"
_TIMEOUT = 60
_LOGGER = logging.getLogger(__name__)


async def _dispatch(
    schema: str,
    uploader: str,
    message: dict[str, Any],
    timestamp: bool = True,
) -> bool:
    """Send a request directly to EDDN."""
    if timestamp:
        message["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    data = {
        "$schemaRef": schema,
        "header": {
            "uploaderID": uploader,
            "softwareName": EDDN.software_name,
            "softwareVersion": EDDN.software_version.base_version,
            "gameversion": EDDN.game_version,
            "gamebuild": EDDN.game_build,
        },
        "message": message,
    }

    headers = {
        "User-Agent": EDDN.user_agent,
        "Content-Type": "application/json",
    }

    async with ClientSession() as session:
        async with session.post(
            _ENDPOINT,
            headers=headers,
            json=data,
            timeout=_TIMEOUT,
        ) as response:
            if response.status == 200:
                return True

            return False


async def commodity(
    station: str,
    system: str,
    market: list[Good],
    market_id: int,
    uploader: str,
) -> bool:
    """Wrapper for sending "/schemas/commodity/3" to EDDN."""

    message = {
        "systemName": system,
        "stationName": station,
        "marketId": market_id,
        "commodities": [
            {
                "name": good.name,
                "meanPrice": good.mean_price,
                "buyPrice": good.stock.price,
                "stock": good.stock.quantity,
                "stockBracket": good.stock.bracket,
                "sellPrice": good.demand.price,
                "demand": good.demand.quantity,
                "demandBracket": good.demand.bracket,
            }
            for good in market
        ],
        "horizons": True,
        "odyssey": True,
    }

    success = await _dispatch(
        "https://eddn.edcd.io/schemas/commodity/3", uploader, message
    )

    market_tritium = next(
        iter(good for good in market if good.name.lower() == "tritium"), None
    )

    if market_tritium:
        _LOGGER.info(
            "Sent EDDN update for '%s' %s %s tonnes of tritium at %s cr/t (%s other orders)",
            station,
            "selling" if market_tritium.stock.quantity > 0 else "buying",
            (
                market_tritium.stock.quantity
                if market_tritium.stock.quantity > 0
                else market_tritium.demand.quantity
            ),
            (
                market_tritium.stock.price
                if market_tritium.stock.quantity > 0
                else market_tritium.demand.price
            ),
            len(market) - 1,
        )
    else:
        _LOGGER.info(
            "Sent EDDN update for '%s' with no tritium (%s other orders)",
            station,
            len(market),
        )

    return success
