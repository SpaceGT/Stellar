"""Fetch and push rescue tasks from the Google Sheet."""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from common import System
from common.enums import Stage
from common.tasks import CarrierRescue, Rescue, ShipRescue
from utils import sheets
from utils.points import Point3D

from .sheet import SPREADSHEET

_LOGGER = logging.getLogger(__name__)

_RESCUE_CHECKS = {
    "Client": (int, None),
    "System": (str, None),
    "Rescuers": (str | None, re.compile(r"^(?:\d+, ?)*(?:\d+)?$", re.MULTILINE)),
    "Tritium": (int | None, None),
    "Message": (int, None),
    "Start": (int, None),
    "End": (int | None, None),
    "State": (str, re.compile(r"^Pending|Underway|Complete|Aborted$", re.MULTILINE)),
}


def _load_rescue(headers: list[str], row: list[Any], index: int) -> Rescue:
    data, missing = sheets.validate_row(
        headers, row, _RESCUE_CHECKS  #  type: ignore [arg-type]
    )

    if missing:
        message = sheets.validation_message(
            missing, _RESCUE_CHECKS  #  type: ignore [arg-type]
        )
        raise ValueError(f"Error loading row {index}\n{message}")

    assert isinstance(data["Rescuers"], str | None)
    if data["Rescuers"] is None:
        rescuers = []
    else:
        rescuers = [
            int(rescuer) for rescuer in data["Rescuers"].replace(" ", "").split(",")
        ]

    progress = {
        "start": datetime.fromtimestamp(data["Start"], timezone.utc),
        "end": (
            datetime.fromtimestamp(data["End"], timezone.utc) if data["End"] else None
        ),
        "stage": Stage(data["State"]),
    }

    # 3D Position is not present on the Sheet (not worth storing)
    location = Point3D(0, 0, 0)

    if data["Tritium"] is None:
        return ShipRescue(
            client=data["Client"],
            message=data["Message"],
            progress=progress,
            rescuers=rescuers,
            system=System(data["System"], location),
        )

    return CarrierRescue(
        client=data["Client"],
        message=data["Message"],
        progress=progress,
        rescuers=rescuers,
        system=System(data["System"], location),
        tritium=data["Tritium"],
    )


async def load_rescues(lazy: bool = False) -> Iterable[Rescue]:
    """Load all the rescue tasks from the Sheet."""
    if not lazy:
        await SPREADSHEET.async_pull()

    sheet = SPREADSHEET["Rescue"]
    headers: list[str] = sheet[0]

    rescues: list[Rescue] = []
    for index, row in enumerate(sheet[1::], start=2):
        try:
            rescue = _load_rescue(headers, row, index)
        except ValueError as error:
            _LOGGER.error(error.args[0])
        else:
            rescues.append(rescue)

    return rescues


async def push_rescues(rescues: Iterable[Rescue]) -> None:
    """Upload all the rescue tasks to the Sheet."""
    sheet = SPREADSHEET["Rescue"]
    headers: list[str] = sheet[0]

    if not set(_RESCUE_CHECKS.keys()).issubset(headers):
        raise ValueError("Cannot push rescue tasks due to header mismatch.")

    for rescue in rescues:
        if str(rescue.message) not in (
            row[headers.index("Message")] for row in sheet[1::]
        ):
            new_row: list[str | float | None] = [""] * len(sheet[0])
            new_row[headers.index("Client")] = str(rescue.client)
            new_row[headers.index("System")] = rescue.system.name
            new_row[headers.index("Rescuers")] = ", ".join(
                str(rescuer) for rescuer in rescue.rescuers
            )

            if isinstance(rescue, CarrierRescue):
                new_row[headers.index("Tritium")] = rescue.tritium
            else:
                new_row[headers.index("Tritium")] = None

            new_row[headers.index("Message")] = str(rescue.message)
            new_row[headers.index("Start")] = int(rescue.progress.start.timestamp())
            new_row[headers.index("End")] = (
                int(rescue.progress.end.timestamp()) if rescue.progress.end else None
            )

            new_row[headers.index("State")] = str(rescue.progress.stage)

            sheet.append(new_row)
            continue

        for row in sheet[1::]:
            if row[headers.index("Message")] != str(rescue.message):
                continue

            if row[headers.index("State")] in [Stage.COMPLETE, Stage.ABORTED]:
                continue

            row[headers.index("Rescuers")] = ", ".join(
                str(rescuer) for rescuer in rescue.rescuers
            )

            if rescue.progress.end:
                row[headers.index("End")] = int(rescue.progress.end.timestamp())

            row[headers.index("State")] = str(rescue.progress.stage)

    await SPREADSHEET.async_push()
