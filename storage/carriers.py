"""Fetch and push carrier depots from the Google Sheet."""

import logging
import re
from datetime import datetime, timezone
from typing import Any

from common import Good, System
from common.depots import Carrier, stock_bracket
from utils import sheets
from utils.points import Point3D

from .sheet import SPREADSHEET

_LOGGER = logging.getLogger(__name__)

_CARRIER_CHECKS = {
    "ID": (str, re.compile(r"^[A-Z0-9]{3}-[A-Z0-9]{3}$", re.MULTILINE)),
    "Name": (str, None),
    "Tonnage": (int | None, None),
    "Price": (int | None, None),
    "Market": (str, re.compile(r"^Buying|Selling|Unlisted$", re.MULTILINE)),
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
}


def _load_market(
    type_: str,
    quantity: int | None,
    price: int | None,
    error_prefix: str = "",
) -> list[Good]:
    market: list[Good] = []
    if type_ == "Unlisted":
        if set([quantity, price]) != set([None]):
            message = "Market is 'Unlisted' but contains tritium!\n"

            if quantity is not None:
                message += f"Tonnage: {quantity} (Expected None)\n"

            if price is not None:
                message += f"Price: {price} (Expected None)\n"

            raise ValueError(error_prefix + message[:-1])

    else:
        if None in (quantity, price):
            message = f"Market is '{type_}' but missing data!\n"

            if quantity is None:
                message += "Tonnage: None (Expected int)\n"

            if price is None:
                message += "Price: None (Expected int)\n"

            raise ValueError(error_prefix + message[:-1])

        assert quantity is not None
        assert price is not None

        info = {
            "price": price,
            "quantity": quantity,
            "bracket": stock_bracket(quantity),
        }
        market.append(
            Good(
                "tritium",
                info if type_ == "Selling" else {},
                info if type_ == "Buying" else {},
            )
        )

    return market


def _load_carrier(headers: list[str], row: list[Any], index: int) -> Carrier | None:
    data, missing = sheets.validate_row(
        headers, row, _CARRIER_CHECKS  # type: ignore [arg-type]
    )

    callsign: str = data["ID"] if "ID" in data else "MISSING"
    name: str = data["Name"] if "Name" in data else "MISSING"

    if missing:
        if "MISSING" == callsign == name:
            suffix = f"row {index}"
        else:
            suffix = f"carrier '[{callsign}] {name}'"

        # Allow skipping inactive carriers
        if "Active" in data and not data["Active"]:
            _LOGGER.warning("Ignoring %s (inactive)", suffix)
            return None

        message = sheets.validation_message(
            missing, _CARRIER_CHECKS  # type: ignore [arg-type]
        )
        raise ValueError(f"Cannot load {suffix}\n{message}")

    error_prefix = f"Cannot load carrier '[{callsign}] {name}'\n"
    try:
        market = _load_market(
            data["Market"], data["Tonnage"], data["Price"], error_prefix
        )
    except ValueError as error:
        if data["Active"]:
            raise error

        _LOGGER.warning("Ignoring '[%s] %s' (inactive)", callsign, name)
        return None

    deploy_location = Point3D(data["X"], data["Y"], data["Z"])

    if data["Current System"] == data["Deploy System"]:
        current_location = Point3D(data["X"], data["Y"], data["Z"])
    else:
        current_location = None  # Not worth storing on sheet

    update = datetime.fromtimestamp(data["Update"], timezone.utc)

    return Carrier(
        name=data["ID"],
        system=System(data["Current System"], current_location),
        deploy_system=System(data["Deploy System"], deploy_location),
        allocated_space=data["Allocated"],
        display_name=data["Name"],
        owner_discord_id=data["Contact"],
        reserve_tritium=data["Reserve"],
        market=market,
        market_id=data["Market ID"],
        inara_url=data["URL"],
        last_update=update,
        active_depot=data["Active"],
    )


async def load_carriers(lazy: bool = False) -> list[Carrier]:
    """Load all the carriers from the Sheet."""
    if not lazy:
        await SPREADSHEET.async_pull()

    sheet = SPREADSHEET["Carrier"]
    headers: list[str] = sheet[0]

    carriers: list[Carrier] = []
    for index, row in enumerate(sheet[1::], start=2):
        try:
            carrier = _load_carrier(headers, row, index)
        except ValueError as error:
            _LOGGER.error(error.args[0])
        else:
            if carrier:
                carriers.append(carrier)

    return carriers


async def push_carriers(carriers: list[Carrier]) -> None:
    """Upload all the carriers to the Sheet."""
    sheet = SPREADSHEET["Carrier"]
    headers: list[str] = sheet[0]

    if not set(_CARRIER_CHECKS.keys()).issubset(headers):
        raise ValueError("Cannot push carriers due to header mismatch.")

    new_rows = 0
    for carrier in carriers:
        if carrier.name not in (row[headers.index("ID")] for row in sheet[1::]):
            new_row: list[str | float | None] = [""] * len(sheet[0])
            new_row[headers.index("ID")] = carrier.name
            new_row[headers.index("Name")] = carrier.display_name

            assert carrier.deploy_system.location
            new_row[headers.index("Deploy System")] = carrier.deploy_system.name
            new_row[headers.index("X")] = carrier.deploy_system.location.x
            new_row[headers.index("Y")] = carrier.deploy_system.location.y
            new_row[headers.index("Z")] = carrier.deploy_system.location.z

            new_row[headers.index("Reserve")] = carrier.reserve_tritium
            new_row[headers.index("Allocated")] = carrier.allocated_space
            new_row[headers.index("Contact")] = str(carrier.owner_discord_id)

            new_row[headers.index("URL")] = carrier.inara_url
            new_row[headers.index("Market ID")] = carrier.market_id
            new_row[headers.index("Active")] = carrier.active_depot

            new_rows += 1
            sheet.append(new_row)

        for row in sheet[1::]:
            if row[headers.index("ID")] != carrier.name:
                continue

            tritium = carrier.tritium

            if tritium:
                if tritium.demand.quantity > 0:
                    row[headers.index("Tonnage")] = tritium.demand.quantity
                    row[headers.index("Price")] = tritium.demand.price
                    row[headers.index("Market")] = "Buying"

                else:
                    row[headers.index("Tonnage")] = tritium.stock.quantity
                    row[headers.index("Price")] = tritium.stock.price
                    row[headers.index("Market")] = "Selling"

            else:
                row[headers.index("Tonnage")] = ""
                row[headers.index("Price")] = ""
                row[headers.index("Market")] = "Unlisted"

            if carrier.capi_status:
                row[headers.index("Synced")] = str(carrier.capi_status)

            row[headers.index("Update")] = int(carrier.last_update.timestamp())
            row[headers.index("Current System")] = carrier.system.name
            row[headers.index("Colour")] = str(carrier.colour)

    if new_rows:
        await SPREADSHEET.async_add_row("Carrier", new_rows)

    await SPREADSHEET.async_push()
