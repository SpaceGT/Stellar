"""Creates buttons used to assign restock tasks."""

import logging
from typing import Callable

from discord import ButtonStyle, Client, Interaction
from discord.ui import Button, View, button

from bot.core import CLIENT
from utils.events import AsyncEvent

from .embed import EmbedBuilder

_LOGGER = logging.getLogger(__name__)


class RestockView(View):
    """View used to assign a restock task."""

    hauler_update = AsyncEvent()
    _can_use: Callable[[int, int, bool], bool] | None = None

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @staticmethod
    def register_can_use(func: Callable[[int, int, bool], bool]) -> None:
        """Function that is used to control if a user can assign themselves."""
        RestockView._can_use = func

    @button(
        label="Volunteer",
        style=ButtonStyle.green,
        emoji="\U0001f6a2",  # :ship:
        custom_id="restock_accept",
    )
    async def restock_accept(self, interaction: Interaction[Client], _: Button) -> None:
        """Assign a user to the task when they click."""

        assert interaction.message

        assert callable(RestockView._can_use)
        valid = RestockView._can_use(  # pylint: disable=not-callable
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

        task_embed = EmbedBuilder.from_embed(interaction.message.embeds[0])

        if interaction.user.id == task_embed.owner_id:
            response = (
                f"{interaction.user.mention}, you have self-assgined yourself "
                + "to help resupply your carrier!\n"
            )
        else:
            response = (
                f"<@{task_embed.owner_id}>, {interaction.user.mention} has volunteered "
                + "to help resupply your carrier!\n"
            )

        response += "## Instructions\n"

        if interaction.user.id != task_embed.owner_id:
            response += "- Agree on a price before embarking.\n"

        assert CLIENT.application

        response += (
            "- Update the market once complete to close this task.\n"
            + f"- Ping {CLIENT.application.owner.mention} with any issues."
        )

        await interaction.response.send_message(content=response)

        await RestockView.hauler_update.fire(
            interaction.message.id, interaction.user.id, True
        )

        _LOGGER.info(
            "%s has volunteered to resupply %s",
            interaction.user.name,
            task_embed.depot,
        )

    @button(
        label="Withdraw",
        style=ButtonStyle.red,
        emoji="\U0001f614",  # :pensive:
        custom_id="restock_withdraw",
    )
    async def restock_withdraw(
        self, interaction: Interaction[Client], _: Button
    ) -> None:
        """Unassign a user to the task when they click."""

        assert interaction.message

        assert callable(RestockView._can_use)
        valid = RestockView._can_use(  # pylint: disable=not-callable
            interaction.message.id, interaction.user.id, False
        )

        if not valid:
            await interaction.response.send_message(
                content="You can't leave what you never had :sweat_smile:",
                ephemeral=True,
            )
            return

        task_embed = EmbedBuilder.from_embed(interaction.message.embeds[0])

        if interaction.user.id == task_embed.owner_id:
            response = (
                f"{interaction.user.mention}, you have decided to no "
                + "longer resupply your carrier!\n"
            )
        else:
            response = (
                f"<@{task_embed.owner_id}>, {interaction.user.mention} withdrew "
                + "their offer to help resupply your carrier!\n"
            )

        await interaction.response.send_message(content=response)

        await RestockView.hauler_update.fire(
            interaction.message.id, interaction.user.id, False
        )

        _LOGGER.info(
            "%s has decided not to resupply %s",
            interaction.user.name,
            task_embed.depot,
        )


def main() -> None:
    """Make the view persistent."""
    CLIENT.add_view(RestockView())
