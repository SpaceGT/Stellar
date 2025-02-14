"""Expose functions to edit discord tasks."""

import logging
from datetime import datetime, timezone
from io import BytesIO

import discord
from discord import ForumChannel

from bot.core import CLIENT
from common import System
from common.enums import Stage
from settings import DISCORD, TIMINGS

from .embed import BaseEmbedBuilder, CarrierEmbedBuilder, ShipEmbedBuilder
from .view import RescueView

_LOGGER = logging.getLogger(__name__)


RESCUER_UPDATE = RescueView.rescuer_update
CLOSE_TASK = RescueView.close_task
REGISTER_CAN_USE = RescueView.register_can_use


def _get_forum() -> ForumChannel:
    forum = CLIENT.get_channel(DISCORD.rescue_channel_id)

    if not isinstance(forum, ForumChannel):
        raise ValueError()

    return forum


def _get_tag(forum: ForumChannel, name: str) -> discord.ForumTag:
    return next(iter(tag for tag in forum.available_tags if tag.name == name))


async def write_revive() -> None:
    """Send a revive message to all inactive threads."""

    task_forum = _get_forum()

    rescuer_revive = (
        "It's been 2 weeks since the last message.\n"
        + f"Any <@&{DISCORD.rescue_role_id}> up for the task?"
    )

    client_app = CLIENT.application
    assert client_app

    progress_revive = (
        "It's been 2 weeks since the last message.\n"
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
                await thread.send(rescuer_revive)

            elif _get_tag(task_forum, Stage.UNDERWAY) in thread.applied_tags:
                await thread.send(progress_revive)


async def write_task(
    client: int,
    system: System,
    tritium: int | None,
    galaxy_map: BytesIO,
) -> int:
    """Write a task to rescue a given user."""
    assert system.location

    task_forum = _get_forum()
    user = await task_forum.guild.fetch_member(client)

    embed: BaseEmbedBuilder
    if tritium is None:
        embed = ShipEmbedBuilder(
            client,
            system.name,
            system.location.magnitude,
            "attachment://image.png",
        )

        _LOGGER.info("Created ship rescue task for %s.", user.name)
    else:
        embed = CarrierEmbedBuilder(
            client,
            system.name,
            system.location.magnitude,
            "attachment://image.png",
            tritium,
        )

        _LOGGER.info(
            "Created carrier rescue task for %s with %s tritium.",
            user.name,
            tritium,
        )

    thread_message = await task_forum.create_thread(
        name=f"{system.name} - <@{client}>",
        embed=embed.embed,
        applied_tags=[_get_tag(task_forum, "Pending")],
        file=discord.File(galaxy_map, filename="image.png"),
        view=RescueView(),
    )

    rescue_role = task_forum.guild.get_role(DISCORD.rescue_role_id)
    assert rescue_role
    role_notification = await thread_message.thread.send(content=rescue_role.mention)
    await role_notification.delete()

    return thread_message.thread.id


async def update_stage(message_id: int, stage: Stage) -> None:
    """Change the stage tag of an existing rescue task."""
    task_forum = _get_forum()
    thread = task_forum.get_thread(message_id)
    assert thread
    await thread.edit(applied_tags=[_get_tag(task_forum, stage)])


async def close_task(message_id: int) -> None:
    """Close a rescue task for a given message."""

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
