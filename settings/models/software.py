"""Handles the software configuration."""

from dataclasses import dataclass
from typing import Any

from packaging.version import Version


@dataclass(frozen=True)
class Software:
    """General software information."""

    name: str
    version: Version
    user_agent: str


def factory(json: dict[str, Any]) -> Software:
    """Create a Software config object."""

    raw_name: str | None = json.get("name")
    raw_version: str = json["version"]
    raw_user_agent: str | None = json.get("user_agent")

    name = raw_name or "Stellar"
    version = Version(raw_version)
    user_agent = raw_user_agent or f"{name}-{version}"

    return Software(name, version, user_agent)
