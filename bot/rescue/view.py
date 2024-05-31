"""Creates buttons used to assign rescue tasks."""

import logging
from typing import Callable

from discord import ButtonStyle, Client, Interaction
from discord.ui import Button, View, button

from bot.core import CLIENT
from utils.events import AsyncEvent

from .embed import BaseEmbedBuilder

_LOGGER = logging.getLogger(__name__)


class RescueView(View):
    """View used to assign a rescue task."""

    rescuer_update = AsyncEvent()
    close_task = AsyncEvent()

    _can_use: Callable[[int, int, bool], bool] | None = None

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @staticmethod
    def register_can_use(func: Callable[[int, int, bool], bool]) -> None:
        """Function that is used to control if a user can assign themselves."""
        RescueView._can_use = func

    @button(
        label="Volunteer",
        style=ButtonStyle.green,
        emoji="\U0001f691",  # :ambulance:
        custom_id="rescue_accept",
    )
    async def rescue_accept(self, interaction: Interaction[Client], _: Button) -> None:
        """Assign a user to the task when they click."""

        assert interaction.message
        assert interaction.guild

        assert callable(RescueView._can_use)
        valid = RescueView._can_use(  # pylint: disable=not-callable
            interaction.message.id, interaction.user.id, True
        )

        if not valid:
            response = (
                "## :eyes: Already Assigned :eyes:\n"
                + "So eager! Put that to good use!"
            )
            await interaction.response.send_message(
                content=response,
                ephemeral=True,
            )
            return

        task_embed = BaseEmbedBuilder.from_base_embed(interaction.message.embeds[0])
        client = await interaction.guild.fetch_member(task_embed.client_id)

        if client.id == interaction.user.id:
            await interaction.response.send_message(
                content="Did you really need a rescue then?",
                ephemeral=True,
            )
            return

        assert CLIENT.application

        response = (
            f"{client.mention}, {interaction.user.mention} has volunteered to help you out!\n"
            + "## Instructions\n"
            + "- Agree on a price before embarking.\n"
            + f"- Ping {CLIENT.application.owner.mention} with any issues."
        )

        await interaction.response.send_message(content=response)

        await RescueView.rescuer_update.fire(
            interaction.message.id, interaction.user.id, True
        )

        _LOGGER.info(
            "%s has volunteered to rescue %s",
            interaction.user.name,
            client.name,
        )

    @button(
        label="Withdraw",
        style=ButtonStyle.red,
        emoji="\U0001f614",  # :pensive:
        custom_id="rescue_withdraw",
    )
    async def rescue_withdraw(
        self, interaction: Interaction[Client], _: Button
    ) -> None:
        """Unassign a user to the task when they click."""

        assert interaction.message
        assert interaction.guild

        assert callable(RescueView._can_use)
        valid = RescueView._can_use(  # pylint: disable=not-callable
            interaction.message.id, interaction.user.id, False
        )

        if not valid:
            await interaction.response.send_message(
                content="You can't leave what you never had :sweat_smile:",
                ephemeral=True,
            )
            return

        task_embed = BaseEmbedBuilder.from_base_embed(interaction.message.embeds[0])
        client = await interaction.guild.fetch_member(task_embed.client_id)

        if client.id == interaction.user.id:
            await interaction.response.send_message(
                content="Ummmm...\nWhy exactly did you come here then? :sob:",
                ephemeral=True,
            )
            return

        response = f"{client.mention}, {interaction.user.mention} withdrew their rescue offer.\n"

        await interaction.response.send_message(content=response)

        await RescueView.rescuer_update.fire(
            interaction.message.id, interaction.user.id, False
        )

        _LOGGER.info(
            "%s has decided not to rescue %s",
            interaction.user.name,
            client.name,
        )

    @button(
        label="Complete",
        style=ButtonStyle.blurple,
        emoji="\u2705",  # :white_check_mark:
        custom_id="rescue_complete",
    )
    async def rescue_complete(
        self, interaction: Interaction[Client], _: Button
    ) -> None:
        """Close the restock task when the client clicks."""

        assert interaction.message
        assert interaction.guild
        assert RescueView.close_task

        task_embed = BaseEmbedBuilder.from_base_embed(interaction.message.embeds[0])
        client = await interaction.guild.fetch_member(task_embed.client_id)

        assert CLIENT.application is not None

        if interaction.user.id not in [
            CLIENT.application.owner.id,
            task_embed.client_id,
        ]:
            response = (
                "## :scroll: Access Denied :scroll:\n"
                + "That is not your choice to make."
            )
            await interaction.response.send_message(
                content=response,
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            content="Task closed :hammer:",
            ephemeral=True,
        )

        await RescueView.close_task.fire(task_embed.client_id)

        _LOGGER.info(
            "Rescue task for %s was marked complete by %s",
            client.name,
            interaction.user.name,
        )


def main() -> None:
    """Make the view persistent."""
    CLIENT.add_view(RescueView())
