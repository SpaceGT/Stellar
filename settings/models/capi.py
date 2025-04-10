"""Handles the Companion API configuration."""

from dataclasses import dataclass
from typing import Any

from .software import Software


@dataclass(frozen=True)
class Capi:
    """Information to use when working with the Companion API."""

    client_id: str
    client_name: str
    redirect_url: str
    user_agent: str
    retry_refresh: bool
    use_epic: bool


def factory(json: dict[str, Any], software: Software | None = None) -> Capi:
    """Create a CAPI config object."""

    client_id: str = json["client_id"]
    redirect_url: str = json["redirect_url"]

    retry_refresh: bool = json["retry_refresh"]
    use_epic: bool = json["use_epic"]

    raw_client_name: str | None = json.get("client_name")
    raw_user_agent: str | None = json.get("user_agent")

    user_agent: str
    client_name: str

    if None in [raw_user_agent, raw_client_name]:
        if software is None:
            raise ValueError

        user_agent = software.user_agent
        client_name = software.name

    else:
        user_agent = raw_user_agent  # type: ignore [assignment]
        client_name = raw_client_name  # type: ignore [assignment]

    return Capi(
        client_id,
        client_name,
        redirect_url,
        user_agent,
        retry_refresh,
        use_epic,
    )
