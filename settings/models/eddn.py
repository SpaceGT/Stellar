"""Handles the EDDN configuration."""

from dataclasses import dataclass
from typing import Any

from packaging.version import Version

from .software import Software


@dataclass(frozen=True)
class Eddn:
    """Information to use when connecting to EDDN."""

    software_name: str
    software_version: Version
    user_agent: str
    game_version: str
    game_build: str


def factory(json: dict[str, Any], software: Software | None = None) -> Eddn:
    """Create an EDDN config object."""

    raw_software_name: str | None = json.get("software_name")
    raw_software_version: str | None = json.get("software_version")
    raw_user_agent: str | None = json.get("user_agent")
    game_version: str = json["game_version"]
    game_build: str = json["game_build"]

    software_name: str
    software_version: Version
    user_agent: str

    if None in [raw_software_name, raw_software_version, raw_user_agent]:
        if software is None:
            raise ValueError

        software_name = software.name
        software_version = software.version
        user_agent = software.user_agent

    else:
        software_name = raw_software_name  # type: ignore [assignment]
        software_version = Version(raw_software_version)  # type: ignore [arg-type]
        user_agent = raw_user_agent  # type: ignore [assignment]

    return Eddn(software_name, software_version, user_agent, game_version, game_build)
