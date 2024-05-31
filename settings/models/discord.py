"""Handles the discord configuration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Discord:
    """Information to use when connecting to Discord."""

    token: str
    hauler_role_id: int
    depot_role_id: int
    rescue_role_id: int
    restock_channel_id: int
    rescue_channel_id: int
    main_guild_id: int
    test_guild_id: int
    alert_channel_id: int
    meme_images: Path


def factory(json: dict[str, Any], env: dict[str, str], config_dir: Path) -> Discord:
    """Create a Discord config object."""

    token: str = env["discord_token"]
    hauler_role_id: int = json["hauler_role_id"]
    depot_role_id: int = json["depot_role_id"]
    rescue_role_id: int = json["rescue_role_id"]
    restock_channel_id: int = json["restock_channel_id"]
    rescue_channel_id: int = json["rescue_channel_id"]
    main_guild_id: int = json["main_guild_id"]
    test_guild_id: int = json["test_guild_id"]
    alert_channel_id: int = json["alert_channel_id"]
    meme_images: Path = config_dir / "media"

    return Discord(
        token,
        hauler_role_id,
        depot_role_id,
        rescue_role_id,
        restock_channel_id,
        rescue_channel_id,
        main_guild_id,
        test_guild_id,
        alert_channel_id,
        meme_images,
    )
