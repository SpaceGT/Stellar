"""Holds the class responsible for loading and checking config files."""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import dotenv
from jsonschema import ValidationError, validate

BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"

_LOGGER = logging.getLogger(__name__)


def _missing_files() -> list[Path]:
    paths: list[Path] = [
        CONFIG_DIR / "config.json",
        CONFIG_DIR / "credentials.json",
        CONFIG_DIR / ".env",
        CONFIG_DIR / "media",
    ]

    return [path for path in paths if not path.exists()]


def _load_json() -> dict[str, Any] | None:
    with open(CONFIG_DIR / "config.json", "r", encoding="utf-8") as file:
        content: dict[str, Any] = json.load(file)

    with open(BASE_DIR / "settings" / "schema.json", "r", encoding="utf-8") as file:
        schema: dict[str, Any] = json.load(file)

    try:
        validate(content, schema)
    except ValidationError:
        return None

    return content


def _load_env() -> dict[str, str] | None:
    dotenv.load_dotenv(CONFIG_DIR / ".env")

    environment = {
        "discord_token": os.getenv("DISCORD_TOKEN"),
        "google_sheet_id": os.getenv("GOOGLE_SHEET_ID"),
    }

    if None in environment.values():
        return None

    return environment  # type: ignore [return-value]


_missing = _missing_files()
if _missing:
    _LOGGER.error(
        "Missing config files: (%s)", ", ".join(f"{path}" for path in _missing)
    )
    sys.exit(1)

_json_data = _load_json()
_env_data = _load_env()

if None in [_json_data, _env_data]:
    if _json_data is None:
        _LOGGER.error("Config schema validation failed!")

    if _env_data is None:
        _LOGGER.error("Missing environment variables!")

    sys.exit(1)

JSON: dict[str, Any] = _json_data  # type: ignore [assignment]
ENV: dict[str, str] = _env_data  # type: ignore [assignment]
