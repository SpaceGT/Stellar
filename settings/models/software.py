"""Handles the software configuration."""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from packaging.version import Version


@dataclass(frozen=True)
class Software:
    """General software information."""

    name: str
    version: Version
    user_agent: str
    webhook: str
    tick: time


def factory(json: dict[str, Any]) -> Software:
    """Create a Software config object."""

    raw_name: str | None = json.get("name")
    raw_version: str = json["version"]
    raw_user_agent: str | None = json.get("user_agent")
    raw_tick: str = json["tick"]

    name = raw_name or "Stellar"
    version = Version(raw_version)
    user_agent = raw_user_agent or f"{name}-{version}"
    webhook: str = json["webhook"]
    tick = datetime.strptime(raw_tick, "%H:%M").time()

    return Software(name, version, user_agent, webhook, tick)
