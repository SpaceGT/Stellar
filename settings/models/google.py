"""Handles the Google configuration."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Google:
    """Information to use when using Google's API."""

    sheet_id: str
    credentials: Path
    token: Path | None


def factory(env: dict[str, str], config_dir: Path) -> Google:
    """Create a Google config object."""

    sheet_id = env["google_sheet_id"]
    credentials = config_dir / "credentials.json"
    raw_token = config_dir / "token.json"

    token = raw_token if raw_token.exists() else None

    return Google(sheet_id, credentials, token)
