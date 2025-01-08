"""Fetch and push restock tasks from the Google Sheet."""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from common import System
from common.enums import Stage
from common.tasks import Restock
from utils import sheets
from utils.points import Point3D

from .sheet import SPREADSHEET

_LOGGER = logging.getLogger(__name__)

_RESTOCK_CHECKS = {
    "ID": (str, re.compile(r"^[A-Z0-9]{3}-[A-Z0-9]{3}$", re.MULTILINE)),
    "Name": (str, None),
    "Required": (int, None),
    "Initial": (int, None),
    "Delivered": (int, None),
    "System": (str, None),
    "Sell Price": (int | None, None),
    "Haulers": (str | None, re.compile(r"^(?:\d+, ?)*(?:\d+)?$", re.MULTILINE)),
    "Message": (int, None),
    "Start": (int, None),
    "End": (int | None, None),
    "State": (str, re.compile(r"^Pending|Underway|Complete|Aborted$", re.MULTILINE)),
}


def _load_restock(headers: list[str], row: list[Any], index: int) -> Restock:
    data, missing = sheets.validate_row(
        headers, row, _RESTOCK_CHECKS  #  type: ignore [arg-type]
    )

    if missing:
        message = sheets.validation_message(
            missing, _RESTOCK_CHECKS  #  type: ignore [arg-type]
        )
        raise ValueError(f"Error loading row {index}\n{message}")

    assert isinstance(data["Haulers"], str | None)
    if data["Haulers"] is None:
        haulers = []
    else:
        haulers = [
            int(hauler) for hauler in data["Haulers"].replace(" ", "").split(",")
        ]

    tritium = {
        "delivered": data["Delivered"],
        "initial": data["Initial"],
        "required": data["Required"],
        "sell_price": data["Sell Price"],
    }

    progress = {
        "start": datetime.fromtimestamp(data["Start"], timezone.utc),
        "end": (
            datetime.fromtimestamp(data["End"], timezone.utc) if data["End"] else None
        ),
        "stage": Stage(data["State"]),
    }

    # 3D Position is not present on the Sheet (not worth storing)
    location = Point3D(0, 0, 0)

    return Restock(
        carrier=(data["ID"], data["Name"]),
        haulers=haulers,
        message=data["Message"],
        tritium=tritium,
        progress=progress,
        system=System(data["System"], location),
    )


async def load_restocks(lazy: bool = False) -> Iterable[Restock]:
    """Load all the restock tasks from the Sheet."""
    if not lazy:
        await SPREADSHEET.async_pull()

    sheet = SPREADSHEET["Restock"]
    headers: list[str] = sheet[0]

    restocks: list[Restock] = []
    for index, row in enumerate(sheet[1::], start=2):
        try:
            restock = _load_restock(headers, row, index)
        except ValueError as error:
            _LOGGER.error(error.args[0])
        else:
            restocks.append(restock)

    return restocks


async def push_restocks(restocks: Iterable[Restock]) -> None:
    """Upload all the restock tasks to the Sheet."""
    sheet = SPREADSHEET["Restock"]
    headers: list[str] = sheet[0]

    if not set(_RESTOCK_CHECKS.keys()).issubset(headers):
        raise ValueError("Cannot push restock tasks due to header mismatch.")

    for restock in restocks:
        if str(restock.message) not in (
            row[headers.index("Message")] for row in sheet[1::]
        ):
            new_row: list[str | float | None] = [""] * len(sheet[0])

            new_row[headers.index("ID")] = restock.carrier[0]
            new_row[headers.index("Name")] = restock.carrier[1]
            new_row[headers.index("Required")] = restock.tritium.required
            new_row[headers.index("Initial")] = restock.tritium.initial
            new_row[headers.index("Delivered")] = restock.tritium.delivered
            new_row[headers.index("System")] = restock.system.name
            new_row[headers.index("Sell Price")] = restock.tritium.sell_price
            new_row[headers.index("Haulers")] = ", ".join(
                str(rescuer) for rescuer in restock.haulers
            )
            new_row[headers.index("Message")] = str(restock.message)
            new_row[headers.index("Start")] = int(restock.progress.start.timestamp())

            new_row[headers.index("End")] = (
                int(restock.progress.end.timestamp()) if restock.progress.end else None
            )

            new_row[headers.index("State")] = str(restock.progress.stage)

            sheet.append(new_row)
            continue

        for row in sheet[1::]:
            if row[headers.index("Message")] != str(restock.message):
                continue

            if row[headers.index("State")] in [Stage.COMPLETE, Stage.ABORTED]:
                continue

            row[headers.index("Required")] = restock.tritium.required
            row[headers.index("Delivered")] = restock.tritium.delivered
            row[headers.index("Sell Price")] = restock.tritium.sell_price

            row[headers.index("Haulers")] = ", ".join(
                str(hauler) for hauler in restock.haulers
            )

            if restock.progress.end:
                row[headers.index("End")] = int(restock.progress.end.timestamp())

            row[headers.index("State")] = str(restock.progress.stage)

    await SPREADSHEET.async_push()
