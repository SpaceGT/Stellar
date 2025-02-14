"""Expose functions to edit discord tasks."""

import logging
from datetime import datetime, timezone
from io import BytesIO

import discord
from discord import ForumChannel, TextChannel

from bot.core import CLIENT
from common.depots import Carrier
from common.enums import Stage
from settings import DISCORD, TIMINGS

from .embed import EmbedBuilder
from .view import RestockView

_LOGGER = logging.getLogger(__name__)

HAULER_UPDATE = RestockView.hauler_update
REGISTER_CAN_USE = RestockView.register_can_use


def _get_forum() -> ForumChannel:
    forum = CLIENT.get_channel(DISCORD.restock_channel_id)

    if not isinstance(forum, ForumChannel):
        raise ValueError()

    return forum


def _get_alert() -> TextChannel:
    channel = CLIENT.get_channel(DISCORD.alert_channel_id)

    if not isinstance(channel, TextChannel):
        raise ValueError()

    return channel


def _get_tag(forum: ForumChannel, name: str) -> discord.ForumTag:
    return next(iter(tag for tag in forum.available_tags if tag.name == name))


async def write_revive() -> None:
    """Send a revive message to all inactive threads."""

    task_forum = _get_forum()

    hauler_revive = (
        "It's been 2 weeks since the last message.\n"
        + f"Any <@&{DISCORD.hauler_role_id}> up for the task?"
    )

    client_app = CLIENT.application
    assert client_app

    owner_revive = (
        "It's been 2 weeks since the last message.\n"
        + "- Try updating the market\n"
        + f"- Notify {client_app.owner.mention} if something is wrong\n"
        + "- Evaluate your current progress"
    )

    for thread in task_forum.threads:
        if _get_tag(task_forum, Stage.COMPLETE) in thread.applied_tags:
            continue

        message = thread.last_message
        if message is None:
            message = [message async for message in thread.history(limit=1)][0]

        if (
            datetime.now(timezone.utc) - message.created_at.astimezone(timezone.utc)
            > TIMINGS.task_revive
        ):
            if _get_tag(task_forum, Stage.PENDING) in thread.applied_tags:
                await thread.send(hauler_revive)

            elif _get_tag(task_forum, Stage.UNDERWAY) in thread.applied_tags:
                await thread.send(owner_revive)


async def write_market_alert(
    discord_id: int, carrier_name: str, last_update: datetime
) -> None:
    """Notify a carrier owner of their outdated market."""

    channel = _get_alert()
    owner = await channel.guild.fetch_member(discord_id)

    last_message = [message async for message in owner.history(limit=1)]
    if (
        last_message
        and datetime.now(timezone.utc)
        - last_message[1].created_at.astimezone(timezone.utc)
        < TIMINGS.market_followup
    ):
        return

    message = (
        f"<@{discord_id}> your carrier `{carrier_name}` has not had a market update "
        + f"for `over {(datetime.now(timezone.utc)-last_update).days//7} weeks`\n"
        + "Please setup CAPI integration (or send an EDDN update) at your earliest convenience!"
    )

    _LOGGER.info(
        "Sending market data warning for '%s' to %s",
        carrier_name,
        owner.name,
    )

    try:
        await owner.send(message)
    except discord.Forbidden:
        _LOGGER.warning(
            "Falling back to %s as %s could not be DMed",
            channel.name,
            owner.name,
        )
        await channel.send(message)


async def write_task(
    carrier: Carrier,
    galaxy_map: BytesIO,
) -> int:
    """Write a task to resupply a given depot."""
    assert carrier.tritium
    assert carrier.tritium.demand.quantity == 0

    task_forum = _get_forum()

    thread_message = await task_forum.create_thread(
        name=f"[{carrier.name}] {carrier.display_name}",
        embed=EmbedBuilder.from_carrier(carrier, "attachment://image.png").embed,
        applied_tags=[_get_tag(task_forum, "Pending")],
        file=discord.File(galaxy_map, filename="image.png"),
        view=RestockView(),
    )

    hauler_role = task_forum.guild.get_role(DISCORD.hauler_role_id)
    assert hauler_role
    role_notification = await thread_message.thread.send(content=hauler_role.mention)
    await role_notification.delete()

    return thread_message.thread.id


async def update_stage(message_id: int, stage: Stage) -> None:
    """Change the stage tag of an existing restock task."""
    task_forum = _get_forum()
    thread = task_forum.get_thread(message_id)
    assert thread
    await thread.edit(applied_tags=[_get_tag(task_forum, stage)])


async def update_task(
    message_id: int,
    stock: int,
    delivered: int,
    target: int,
) -> None:
    """Update a resupply task for a given message."""

    task_forum = _get_forum()

    # First message and threads share the same ID
    thread = task_forum.get_thread(message_id)
    assert thread
    message = await thread.fetch_message(message_id)

    task_embed = EmbedBuilder.from_embed(message.embeds[0], "attachment://image.png")
    task_embed.stock = stock
    task_embed.delivered = delivered
    task_embed.target = target

    await message.edit(embed=task_embed.embed)


async def close_task(message_id: int) -> None:
    """Close the resupply task for a given message."""

    task_forum = _get_forum()

    # First message and threads share the same ID
    thread = task_forum.get_thread(message_id)
    assert thread
    message = await thread.fetch_message(message_id)

    await message.edit(view=None)
    await thread.edit(
        locked=True,
        archived=True,
        applied_tags=[_get_tag(task_forum, "Complete")],
    )
