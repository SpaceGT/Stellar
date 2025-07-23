"""Handles the webhook configuration."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Webhooks:
    """Webhook information."""

    fallback: str | None
    critical: str | None
    error: str | None
    warning: str | None
    info: str | None
    debug: str | None


def factory(json: dict[str, Any]) -> Webhooks:
    """Create a Webhooks config object."""

    fallback: str | None = json.get("fallback")
    critical: str | None = json.get("critical")
    error: str | None = json.get("error")
    warning: str | None = json.get("warning")
    info: str | None = json.get("info")
    debug: str | None = json.get("debug")

    return Webhooks(fallback, critical, error, warning, info, debug)
