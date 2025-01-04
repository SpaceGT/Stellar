"""Allows working with the Spansh API"""

from typing import Any

from aiohttp import ClientSession
from thefuzz import process  # type: ignore [import-untyped]

from settings import SOFTWARE

_TIMEOUT = 60
_SYSTEM_URL = "https://spansh.co.uk/api/systems"


async def _request(url: str) -> dict[str, Any]:
    headers = {"User-Agent": SOFTWARE.user_agent}

    async with ClientSession() as session:
        async with session.get(f"{url}", headers=headers, timeout=_TIMEOUT) as response:
            if response.status != 200:
                response.raise_for_status()

            data: dict[str, Any] = await response.json()

    return data


async def predict_system(name: str) -> list[str]:
    """Return a confidence-ordered list of system names based on a partial name."""

    response = await _request(f"{_SYSTEM_URL}/field_values/system_names?q={name}")
    if response is None:
        return []

    systems = response["values"]

    output = [
        system
        for system, _ in process.extract(
            name,
            systems,
            processor=str,
            limit=len(systems),
        )
    ]

    return output
