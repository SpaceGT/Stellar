"""Prompt shown to clients when requesting a rescue."""

import logging

import discord
from discord import ButtonStyle, Client, Interaction
from discord.ui import Button, Modal, TextInput, View, button

import settings
from bot.core import CLIENT
from external import edsm
from services.rescues import RESCUE_SERVICE

_LOGGER = logging.getLogger(__name__)

_MESSAGE = """
# Welcome to the STAR Rescue Centre
Stuck or out of tritium?
You've come to the right place!
## :rocket: Ships
We rescue ships that are stuck in systems outside their jump range.
Please contact the [Fuel Rats](<https://fuelrats.com/i-need-fuel>) or the [Hull Seals](<https://hullseals.space/>) before requesting a rescue.
## :ship: Carriers
We will provide advice and support to get you moving again no matter where you are.
Please be prepared to pay at least **150,000**cr/t of tritium if a rescue carrier comes to you.

_You can request a rescue by clicking the button below and filling in the form._
"""


class Prompt(Modal, title="Rescue Info"):
    """Prompt shown to clients when requesting a rescue."""

    system = TextInput(label="System Name", placeholder="Ministry")
    tritium = TextInput(label="Tritium Required", placeholder="0", required=False)

    async def on_submit(  # pylint: disable=arguments-differ
        self, interaction: discord.Interaction[Client]
    ) -> None:
        """Open a modal where a resupply task can be requested."""
        system_info = await edsm.system(self.system.value)

        if system_info is None:
            response = (
                "## :x: Bad System :x:\nThe system "
                + f"`{self.system.value}` was not recognised!\n"
            )
            _LOGGER.info(
                "Rescue modal from %s has unrecognised system '%s'",
                interaction.user.name,
                self.system.value,
            )
            await interaction.response.send_message(response, ephemeral=True)
            return

        if self.tritium.value:
            try:
                tritium = int(self.tritium.value)
            except ValueError:
                response = "## :x: Bad Tritium :x:\nPlease enter an integer!\n"
                _LOGGER.info(
                    "Rescue modal from %s has invalid tritium '%s'",
                    interaction.user.name,
                    self.tritium.value,
                )
                await interaction.response.send_message(response, ephemeral=True)
                return
        else:
            tritium = None

        _LOGGER.info(
            "Processed rescue modal from %s with %s tritium",
            interaction.user.name,
            self.tritium.value,
        )
        await RESCUE_SERVICE.new_rescue(interaction.user.id, system_info, tritium)


class Request(View):
    """View used to request a rescue task."""

    def __init__(self):
        super().__init__(timeout=None)

    @button(
        label="Request Rescue",
        style=ButtonStyle.blurple,
        emoji="\U0001f691",  # :ambulance:
        custom_id="rescue_request",
    )
    async def request_rescue(
        self,
        interaction: Interaction[Client],
        _: Button,
    ) -> None:
        """Open a modal where a rescue task can be requested."""
        await interaction.response.send_modal(Prompt())
        _LOGGER.info("Send rescue modal to %s.", interaction.user.name)


async def ensure_message() -> None:
    """Make sure the rescue message and button exists."""

    forum = CLIENT.get_channel(settings.DISCORD.rescue_channel_id)
    assert isinstance(forum, discord.ForumChannel)
    thread = next(iter(thread for thread in forum.threads if thread.flags.pinned), None)

    if thread:
        message = await thread.fetch_message(thread.id)

        if message.author.id == CLIENT.user.id:
            _LOGGER.info("Using existing persistent rescue message.")
            return

    new_thread_message = await forum.create_thread(
        name="Rescue Center Info",
        content=_MESSAGE,
        view=Request(),
    )

    await new_thread_message.thread.edit(pinned=True)
    _LOGGER.info("Created new persistent rescue message.")


def main() -> None:
    """Make the view persistent."""
    CLIENT.add_view(Request())
