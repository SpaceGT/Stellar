"""Load an abstracted Google Sheet as a matrix."""

import asyncio
import copy
import logging
import typing
from collections.abc import Iterator
from pathlib import Path
from re import Pattern
from types import UnionType
from typing import Any

from google.auth.transport.requests import Request  # type: ignore [import-untyped]
from google.oauth2.credentials import Credentials  # type: ignore [import-untyped]
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore [import-untyped]
from googleapiclient.discovery import build
from googleapiclient.http import HttpError  # type: ignore [import-untyped]

_LOGGER = logging.getLogger(__name__)


def implicit_cast(value: Any, _type: type) -> Any:
    """Silently try to cast a value to a given type."""

    if issubclass(_type, float) and isinstance(value, int):
        return float(value)

    if issubclass(_type, int) and isinstance(value, str):
        if value.isdigit():
            return int(value)

    return value


def validate_row(
    headers: list[str],
    row: list[Any],
    checks: dict[str, tuple[type, Pattern[str] | None]],
    strict: bool = False,
) -> tuple[dict[str, Any], dict[str, Any | None]]:
    """Validates a row with type checking and optional regex."""

    loaded: dict[str, Any] = {}
    invalid: dict[str, Any | None] = {}

    for key in checks:
        allow_none = False

        _type = checks[key][0]
        regex = checks[key][1]

        # Allow for loading None types through a union
        if typing.get_origin(_type) is UnionType:
            args = typing.get_args(_type)

            if len(args) != 2 and args[1] is not None:
                raise ValueError

            _type = args[0]
            allow_none = True

        if key not in headers:
            invalid[key] = None
            continue

        value = row[headers.index(key)]

        # Empty string means a blank cell
        if value == "":
            if allow_none:
                loaded[key] = None
            else:
                invalid[key] = None
            continue

        if not strict:
            value = implicit_cast(value, _type)

        if not isinstance(value, _type):
            invalid[key] = value
            continue

        if regex and not regex.match(str(value)):
            invalid[key] = value
            continue

        loaded[key] = value

    return loaded, invalid


def validation_message(
    missing: dict[str, Any | None],
    checks: dict[str, tuple[type, Pattern[str] | None]],
) -> str:
    """Generates a human-readable message on why a row failed validation."""
    messages: list[str] = []

    for key, value in missing.items():
        received = f"{key}: {repr(value)}"

        details: tuple[type | UnionType, Pattern[str] | None] = checks[key]
        if typing.get_origin(details[0]) is UnionType:
            expected = f"Expected {typing.get_args(details[0])[0].__name__} | None"
        else:
            expected = f"Expected {details[0].__name__}"  # type: ignore [union-attr]

        if details[1] is not None:
            expected += f" matching '{details[1].pattern}'"

        messages.append(f"{received} ({expected})")

    return "\n".join(messages)


def load_credentials(credentials_path: Path, token_path: Path | None) -> Credentials:
    """Load application credentials from file."""
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = None

    if token_path and token_path.is_file():
        credentials = Credentials.from_authorized_user_file(
            str(token_path.absolute()), scopes
        )

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path.absolute()), scopes
            )
            credentials = flow.run_local_server(port=0)

        if token_path:
            with open(token_path, "w", encoding="utf-8") as token:
                token.write(credentials.to_json())

    return credentials


class GoogleSheet:
    """Load an abstracted Google Sheet as a matrix."""

    _NOT_LOADED = AttributeError("Remote Sheet has not been loaded.")

    def __init__(self, spreadsheet_id: str, credentials: Credentials) -> None:
        self._spreadsheet_id = spreadsheet_id
        self._credentials = credentials
        self._remote_data: dict[str, list[list[Any]]] = {}
        self._local_data: dict[str, list[list[Any]]] = {}
        self._loaded = False

    def __str__(self) -> str:
        return f"{self._spreadsheet_id}"

    def __getitem__(self, key: str) -> list[list[Any]]:
        if not self._loaded:
            raise GoogleSheet._NOT_LOADED

        return self._local_data[key]

    def __len__(self) -> int:
        if not self._loaded:
            raise GoogleSheet._NOT_LOADED

        cells = 0
        for sheet in self._local_data.values():
            for row in sheet:
                cells += len(row)

        return cells

    def __iter__(self) -> Iterator[str]:
        if not self._loaded:
            raise GoogleSheet._NOT_LOADED

        return iter(self._local_data)

    @staticmethod
    def _get_index_label(index: int) -> str:
        """Convert an column index into its alphabetic label."""
        if index < 0:
            return ""

        quotient, remainder = divmod(index, 26)
        letter = chr(remainder + ord("A"))

        return GoogleSheet._get_index_label(quotient - 1) + letter

    def _verify_credentials(self) -> bool:
        """Refresh credentials using the refresh_token if applicable."""
        if self._credentials.valid:
            return True

        if self._credentials.expired and self._credentials.refresh_token:
            self._credentials.refresh(Request())
            return True

        return False

    def _get_sheet_differences(self) -> list[dict[str, Any]]:
        """Return a list of differences between the local and remote Google Sheet."""
        differences: list[dict[str, Any]] = []
        for sheet_name in self._local_data.keys():
            local_sheet = self._local_data[sheet_name]
            remote_sheet = self._remote_data[sheet_name]

            for row_index, local_row in enumerate(local_sheet):
                for column_index, local_cell in enumerate(local_row):
                    remote_cell: Any

                    try:
                        remote_cell = remote_sheet[row_index][column_index]
                    except IndexError:
                        remote_cell = ""

                    if local_cell != remote_cell:
                        cell_range = (
                            f"{sheet_name}"
                            + f"!{GoogleSheet._get_index_label(column_index)}"
                            + f"{row_index+1}"
                        )
                        differences.append(
                            {
                                "range": cell_range,
                                "local": local_cell,
                                "remote": remote_cell,
                            }
                        )

        return differences

    def pull(self) -> None:
        """Fetch the latest version of the Google Sheet."""
        if not self._verify_credentials():
            raise PermissionError("Invalid google sheet token.")

        service = build(
            "sheets", "v4", credentials=self._credentials, cache_discovery=False
        )

        if hasattr(service, "spreadsheets"):
            sheets = service.spreadsheets()
        else:
            raise ValueError

        try:
            spreadsheet = sheets.get(spreadsheetId=self._spreadsheet_id).execute()

            for sheet in spreadsheet["sheets"]:
                title = sheet["properties"]["title"]

                values = (
                    sheets.values()
                    .get(
                        spreadsheetId=self._spreadsheet_id,
                        valueRenderOption="UNFORMATTED_VALUE",
                        range=title,
                    )
                    .execute()
                    .get("values", [])
                )

                self._remote_data |= {f"{title}": values}

        except HttpError as error:
            if error.status_code in (500, 502, 503):
                _LOGGER.warning("Pull failed due to unavailable sheet.")
            else:
                raise error
        except TimeoutError:
            _LOGGER.warning("Pull failed to socket timeout.")
        else:
            self._local_data = copy.deepcopy(self._remote_data)
            self._loaded = True

    async def async_pull(self) -> None:
        """Asynchronously fetch the latest version of the Google Sheet."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.pull)

    def push(self) -> None:
        """Push all the changes to the Google Sheet."""
        if not self._verify_credentials():
            raise PermissionError("Invalid google sheet token.")

        if not self._loaded:
            raise GoogleSheet._NOT_LOADED

        data: list[dict[str, Any]] = []
        for update in self._get_sheet_differences():
            data.append({"range": update["range"], "values": [[update["local"]]]})

        if not data:
            return

        request_body = {"valueInputOption": "USER_ENTERED", "data": data}

        service = build(
            "sheets", "v4", credentials=self._credentials, cache_discovery=False
        )

        if hasattr(service, "spreadsheets"):
            sheets = service.spreadsheets()
        else:
            raise ValueError

        try:
            sheets.values().batchUpdate(
                spreadsheetId=self._spreadsheet_id, body=request_body
            ).execute()
        except HttpError as error:
            if error.status_code in (500, 502, 503):
                _LOGGER.warning("Push failed due to unavailable sheet.")
            else:
                raise error
        except TimeoutError:
            _LOGGER.warning("Push failed to socket timeout.")
        else:
            self._remote_data = copy.deepcopy(self._local_data)

    async def async_push(self) -> None:
        """Asynchronously push all the changes to the Google Sheet."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.push)

    def add_row(self, sheet_name: str, count: int = 1) -> None:
        """Creates a new row at the bottom of the sheet."""

        service = build(
            "sheets", "v4", credentials=self._credentials, cache_discovery=False
        )

        if hasattr(service, "spreadsheets"):
            sheets = service.spreadsheets()
        else:
            raise ValueError

        try:
            spreadsheet = sheets.get(spreadsheetId=self._spreadsheet_id).execute()

            sheet_id = None
            for sheet in spreadsheet["sheets"]:
                if sheet["properties"]["title"] == sheet_name:
                    sheet_id = sheet["properties"]["sheetId"]
            assert sheet_id is not None

            request_body = {
                "requests": [
                    {
                        "appendDimension": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "length": count,
                        }
                    }
                ]
            }

            sheets.batchUpdate(
                spreadsheetId=self._spreadsheet_id, body=request_body
            ).execute()

        except HttpError as error:
            if error.status_code in (500, 502, 503):
                _LOGGER.warning("Row creation failed due to unavailable sheet.")
            else:
                raise error
        except TimeoutError:
            _LOGGER.warning("Row creation failed to socket timeout.")

    async def async_add_row(self, sheet_name: str, count: int = 1) -> None:
        """Asynchronously create a new row at the bottom of the sheet."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.add_row, sheet_name, count)
