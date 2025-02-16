"""Allows working with the Spansh API"""

from typing import Any

from aiohttp import ClientSession
from thefuzz import process  # type: ignore [import-untyped]

from common import System
from settings import SOFTWARE
from utils.points import Point3D

_TIMEOUT = 60
_URL = "https://spansh.co.uk/api"


async def _request(url: str) -> dict[str, Any]:
    headers = {"User-Agent": SOFTWARE.user_agent}

    async with (
        ClientSession(raise_for_status=True) as session,
        session.get(url, headers=headers, timeout=_TIMEOUT) as response,
    ):
        data: dict[str, Any] = await response.json()

    return data


async def predict_system(name: str) -> list[str]:
    """Return a confidence-ordered list of system names based on a partial name."""

    response = await _request(f"{_URL}/systems/field_values/system_names?q={name}")
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


async def nearest_system(location: Point3D) -> System:
    """Return the closest known system to a location."""

    response = await _request(
        f"{_URL}/nearest?x={location.x}&y={location.y}&z={location.z}"
    )
    system = System(
        response["system"]["name"],
        Point3D(
            response["system"]["x"],
            response["system"]["y"],
            response["system"]["z"],
        ),
    )

    return system
