"""Expose functions to manage discord CAPI integration."""

import logging
from datetime import datetime, timezone

import discord
from discord import TextChannel

from bot.core import CLIENT
from common.enums import Service
from settings import DISCORD, TIMINGS

_LOGGER = logging.getLogger(__name__)


def _get_alert() -> TextChannel:
    channel = CLIENT.get_channel(DISCORD.alert_channel_id)

    if not isinstance(channel, TextChannel):
        raise ValueError()

    return channel


async def write_capi_alert(discord_id: int, commander: str, auth_type: str) -> None:
    """Notify a user of their expired CAPI token."""
    assert CLIENT.user

    channel = _get_alert()
    owner = await channel.guild.fetch_member(discord_id)
    guild = CLIENT.get_guild(DISCORD.main_guild_id)
    assert guild

    last_message = [message async for message in owner.history(limit=1)]
    if (
        last_message
        and datetime.now(timezone.utc)
        - last_message[1].created_at.astimezone(timezone.utc)
        < TIMINGS.capi_followup
    ):
        return

    if auth_type == Service.EPIC:
        message = (
            f"<@{discord_id}> your CAPI token for `{commander}` could not be refreshed.\n"
            + f"- This is a problem with `{Service.EPIC}` (not {CLIENT.user.mention})\n"
            + "- Try running `Elite Dangerous` during your next attempt\n\n"
            + f"Please run `/capi` in `{guild.name}` and re-auth.\n"
        )
        _LOGGER.info("Sending CAPI Epic warning '%s' to %s", commander, owner.name)
    else:
        message = (
            f"<@{discord_id}> your CAPI token for `{commander}` could not be refreshed.\n"
            + f"Please run `/capi` in `{guild.name}` and re-auth.\n"
        )
        _LOGGER.info("Sending CAPI token warning for '%s' to %s", commander, owner.name)

    try:
        await owner.send(message)
    except discord.Forbidden:
        _LOGGER.warning(
            "Falling back to %s as %s could not be DMed",
            channel.name,
            owner.name,
        )
        await channel.send(message)
