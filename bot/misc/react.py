"""Flood a message with reactions."""

import logging
import re
from re import Match, Pattern
from typing import Final

import discord
from discord import Client, Interaction, TextChannel, app_commands
from discord.ext import commands

from bot.core import CLIENT
from settings import DISCORD

_LOGGER = logging.getLogger(__name__)


class React(commands.Cog):
    """Flood a message with reactions."""

    _REGEX: Final[Pattern[str]] = re.compile(
        r"https:\/\/discord\.com\/channels\/(\d+)\/(\d+)\/(\d+)"
    )

    _SUCCESS: Final[str] = (
        "## :sunglasses: Reaction Complete :sunglasses:\n"
        + "You must be **really** cool."
    )

    _ERROR: Final[str] = (
        "## :link: Bad Link :link:\n"
        + "Ensure you entered a valid Discord message link."
    )

    _FORBIDDEN: Final[str] = (
        "## :cross_mark: Bad Link :cross_mark:\n"
        + "Missing required permissions to react."
    )

    def __init__(self) -> None:
        self._reacts = [
            "\U0001f389",  # :tada:
            "\u2705",  # :white_check_mark:
            "\U0001f525",  # :fire:
            "\u2b06",  # :arrow_up:
            "\U0001f44c\U0001f3fb",  # :ok_hand_tone1:
            "\u2b50",  # :star:
            "\U0001f60e",  # :sunglasses:
            "\U0001f607",  # :innocent:
            "\U0001f440",  # :eyes:
        ]

    @staticmethod
    def _parse_link(link: str) -> tuple[int, int, int] | None:
        match: Match[str] | None = React._REGEX.match(link)

        if not match:
            return None

        guild_id: int = int(match.group(1))
        channel_id: int = int(match.group(2))
        message_id: int = int(match.group(3))

        return guild_id, channel_id, message_id

    @app_commands.command(  # type: ignore [arg-type]
        name="react",
        description="Express how much a message means to you.",
    )
    @app_commands.describe(message="Discord link to the message.")
    async def react(self, interaction: Interaction[Client], message: str) -> None:
        """Express how much a message means to you."""

        info = React._parse_link(message)

        if not info:
            await interaction.response.send_message(React._ERROR, ephemeral=True)
            return

        _, channel_id, message_id = info

        try:
            channel = await interaction.client.fetch_channel(channel_id)
        except discord.Forbidden:
            await interaction.response.send_message(React._FORBIDDEN, ephemeral=True)
            return

        if not isinstance(channel, TextChannel):
            await interaction.response.send_message(React._ERROR, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        target = await channel.fetch_message(message_id)

        for react in self._reacts:
            await target.add_reaction(react)

        _LOGGER.info("Reacted to %s on behalf of %s", message, interaction.user.name)

        await interaction.followup.send(React._SUCCESS, ephemeral=True)


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(React(), DISCORD.main_guild_id)
