"""Fetch and push Colonia Bridge stations from the Google Sheet."""

import re
from datetime import datetime, timezone
from typing import Any

from common import Good, System
from common.depots import Bridge
from utils import sheets
from utils.points import Point3D

from .sheet import SPREADSHEET

_BRIDGE_CHECKS = {
    "Name": (str, None),
    "Tonnage": (int, None),
    "Sell Price": (int, None),
    "Market ID": (int, None),
    "Update": (int, None),
    "System": (str, None),
    "X": (float, None),
    "Y": (float, None),
    "Z": (float, None),
    "URL": (str, re.compile(r"^https:\/\/inara\.cz\/station\/\d+$", re.MULTILINE)),
}


def _load_bridge(headers: list[str], row: list[Any]) -> Bridge:
    data, missing = sheets.validate_row(headers, row, _BRIDGE_CHECKS)

    if missing:
        raise ValueError(
            f"Error loading bridge: {list(zip(headers, row))} (missing {missing})"
        )

    # Stock bracket and demand are not present on the Sheet (not worth storing)
    tritium = Good(
        "tritium",
        {
            "price": data["Sell Price"],
            "quantity": data["Tonnage"],
            "bracket": 0,
        },
        {},
    )
    location = Point3D(data["X"], data["Y"], data["Z"])

    update = datetime.fromtimestamp(data["Update"], timezone.utc)

    return Bridge(
        name=data["Name"],
        system=System(data["System"], location),
        market=[tritium],
        market_id=data["Market ID"],
        inara_url=data["URL"],
        last_update=update,
    )


async def load_bridges(lazy: bool = False) -> list[Bridge]:
    """Load all the bridges from the Sheet."""
    if not lazy:
        await SPREADSHEET.async_pull()

    sheet = SPREADSHEET["Bridge"]
    headers: list[str] = sheet[0]

    bridges = [_load_bridge(headers, row) for row in sheet[1::]]
    return bridges


async def push_bridges(bridges: list[Bridge]) -> None:
    """Upload all the bridges to the Sheet."""
    sheet = SPREADSHEET["Bridge"]
    headers: list[str] = sheet[0]

    if not set(_BRIDGE_CHECKS.keys()).issubset(headers):
        raise ValueError("Cannot push bridges due to header mismatch.")

    for bridge in bridges:
        for row in sheet[1::]:
            if row[headers.index("Name")] != bridge.name:
                continue

            tritium = bridge.tritium

            if tritium:
                row[headers.index("Tonnage")] = tritium.stock.quantity
                row[headers.index("Sell Price")] = tritium.stock.price

            else:
                row[headers.index("Tonnage")] = 0

            row[headers.index("Update")] = int(bridge.last_update.timestamp())

    await SPREADSHEET.async_push()
