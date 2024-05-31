"""Fetch and push carrier depots from the Google Sheet."""

import re
from datetime import datetime, timezone
from typing import Any

from common import Good, System
from common.depots import Carrier, stock_bracket
from utils import sheets
from utils.points import Point3D

from .sheet import SPREADSHEET

_CARRIER_CHECKS = {
    "ID": (str, re.compile(r"^[A-Z0-9]{3}-[A-Z0-9]{3}$", re.MULTILINE)),
    "Name": (str, None),
    "Tonnage": (int, None),
    "Price": (int, None),
    "Market": (str, re.compile(r"^Buying|Selling$", re.MULTILINE)),
    "Update": (int, None),
    "Current System": (str, None),
    "X": (float, None),
    "Y": (float, None),
    "Z": (float, None),
    "Reserve": (int, None),
    "Allocated": (int, None),
    "Deploy System": (str, None),
    "Contact": (int, None),
    "URL": (str, re.compile(r"^https:\/\/inara\.cz\/station\/\d+$", re.MULTILINE)),
    "Market ID": (int, None),
    "Active": (bool, None),
    "Poll": (bool, None),
}


def _load_carrier(headers: list[str], row: list[Any]) -> Carrier:
    data, missing = sheets.validate_row(headers, row, _CARRIER_CHECKS)

    if missing:
        raise ValueError(
            f"Error loading carrier: {list(zip(headers, row))} (missing {missing})"
        )

    market = {
        "price": data["Price"],
        "quantity": data["Tonnage"],
        "bracket": stock_bracket(data["Tonnage"]),
    }
    tritium = Good(
        "tritium",
        market if data["Market"] == "Selling" else {},
        market if data["Market"] == "Buying" else {},
    )

    deploy_location = Point3D(data["X"], data["Y"], data["Z"])

    if data["Current System"] == data["Deploy System"]:
        current_location = Point3D(data["X"], data["Y"], data["Z"])
    else:
        current_location = Point3D(0, 0, 0)  # Not worth storing on sheet

    update = datetime.fromtimestamp(data["Update"], timezone.utc)

    return Carrier(
        name=data["ID"],
        system=System(data["Current System"], current_location),
        deploy_system=System(data["Deploy System"], deploy_location),
        restock_status=None,
        allocated_space=data["Allocated"],
        display_name=data["Name"],
        owner_discord_id=data["Contact"],
        reserve_tritium=data["Reserve"],
        market=[tritium],
        market_id=data["Market ID"],
        inara_url=data["URL"],
        last_update=update,
        active_depot=data["Active"],
        inara_poll=data["Poll"],
    )


async def load_carriers(lazy: bool = False) -> list[Carrier]:
    """Load all the carriers from the Sheet."""
    if not lazy:
        await SPREADSHEET.async_pull()

    sheet = SPREADSHEET["Carrier"]
    headers: list[str] = sheet[0]

    carriers = [_load_carrier(headers, row) for row in sheet[1::]]
    return carriers


async def push_carriers(carriers: list[Carrier]) -> None:
    """Upload all the carriers to the Sheet."""
    sheet = SPREADSHEET["Carrier"]
    headers: list[str] = sheet[0]

    if not set(_CARRIER_CHECKS.keys()).issubset(headers):
        raise ValueError("Cannot push carriers due to header mismatch.")

    for carrier in carriers:
        for row in sheet[1::]:
            if row[headers.index("ID")] != carrier.name:
                continue

            tritium = carrier.tritium

            if tritium:
                if tritium.stock.quantity > 0:
                    row[headers.index("Tonnage")] = tritium.stock.quantity
                    row[headers.index("Price")] = tritium.stock.price
                    row[headers.index("Market")] = "Selling"

                if tritium.demand.quantity > 0:
                    row[headers.index("Tonnage")] = tritium.demand.quantity
                    row[headers.index("Price")] = tritium.demand.price
                    row[headers.index("Market")] = "Buying"

            else:
                row[headers.index("Tonnage")] = 0

            row[headers.index("Update")] = int(carrier.last_update.timestamp())
            row[headers.index("Current System")] = carrier.system.name

            row[headers.index("Colour")] = str(carrier.colour)

    await SPREADSHEET.async_push()
