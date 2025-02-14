"""Fetch and push Companion API information from the Google Sheet."""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from common import CapiData
from utils import sheets

from .sheet import SPREADSHEET

_LOGGER = logging.getLogger(__name__)


_CAPI_CHECKS = {
    "Account": (int, None),
    "Type": (str, re.compile(r"^Frontier|Steam|Epic$", re.MULTILINE)),
    "Commander": (str, None),
    "Carrier": (str | None, re.compile(r"^[A-Z0-9]{3}-[A-Z0-9]{3}$", re.MULTILINE)),
    "Discord": (int, None),
    "Access Token": (str | None, None),
    "Expiry": (int | None, None),
    "Refresh Token": (str, None),
}


def _load_row(headers: list[str], row: list[Any], index: int) -> CapiData:
    data, missing = sheets.validate_row(
        headers, row, _CAPI_CHECKS  #  type: ignore [arg-type]
    )

    if missing:
        message = sheets.validation_message(
            missing, _CAPI_CHECKS  #  type: ignore [arg-type]
        )
        raise ValueError(f"Error loading row {index}\n{message}")

    if data["Access Token"] and data["Expiry"]:
        expiry = datetime.fromtimestamp(data["Expiry"], timezone.utc)
        token = (data["Access Token"], expiry)

    elif not data["Access Token"] and not data["Expiry"]:
        token = None

    else:
        raise ValueError(
            f"Error loading row {index}\n"
            + "'Access Token' and 'Expiry' must come in pairs."
        )

    return CapiData(
        customer_id=data["Account"],
        auth_type=data["Type"],
        commander=data["Commander"],
        carrier=data["Carrier"],
        discord_id=data["Discord"],
        access_token=token,
        refresh_token=data["Refresh Token"],
    )


async def load_data(lazy: bool = False) -> Iterable[CapiData]:
    """Load all the CAPI data from the Sheet."""
    if not lazy:
        await SPREADSHEET.async_pull()

    sheet = SPREADSHEET["CAPI"]
    headers: list[str] = sheet[0]

    data: list[CapiData] = []
    for index, row in enumerate(sheet[1::], start=2):
        try:
            info = _load_row(headers, row, index)
        except ValueError as error:
            _LOGGER.error(error.args[0])
        else:
            data.append(info)

    return data


async def push_data(data: Iterable[CapiData]) -> None:
    """Upload all the CAPI data to the Sheet."""
    sheet = SPREADSHEET["CAPI"]
    headers: list[str] = sheet[0]

    if not set(_CAPI_CHECKS.keys()).issubset(headers):
        raise ValueError("Cannot push CAPI data due to header mismatch.")

    for info in data:
        if str(info.customer_id) not in (
            row[headers.index("Account")] for row in sheet[1::]
        ):
            new_row: list[str | float | None] = [""] * len(sheet[0])

            new_row[headers.index("Account")] = str(info.customer_id)
            new_row[headers.index("Type")] = info.auth_type
            new_row[headers.index("Commander")] = info.commander
            new_row[headers.index("Carrier")] = info.carrier or ""
            new_row[headers.index("Discord")] = str(info.discord_id)
            new_row[headers.index("Refresh Token")] = info.refresh_token

            if info.access_token:
                new_row[headers.index("Access Token")] = info.access_token[0]
                new_row[headers.index("Expiry")] = int(info.access_token[1].timestamp())
            else:
                new_row[headers.index("Access Token")] = ""
                new_row[headers.index("Expiry")] = ""

            sheet.append(new_row)
            continue

        for row in sheet[1::]:
            if row[headers.index("Account")] != str(info.customer_id):
                continue

            row[headers.index("Type")] = info.auth_type
            row[headers.index("Commander")] = info.commander
            row[headers.index("Carrier")] = info.carrier or ""
            row[headers.index("Refresh Token")] = info.refresh_token

            if info.access_token:
                row[headers.index("Access Token")] = info.access_token[0]
                row[headers.index("Expiry")] = int(info.access_token[1].timestamp())
            else:
                row[headers.index("Access Token")] = ""
                row[headers.index("Expiry")] = ""

    await SPREADSHEET.async_push()
