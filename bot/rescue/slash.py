"""Manually manage rescue tasks."""

import re

from discord import Client, Interaction, User, app_commands
from discord.app_commands import Choice
from discord.ext import commands

from bot.core import CLIENT
from common.tasks.rescue import Rescue
from services import RESCUE_SERVICE
from settings import DISCORD


def _autocomplete(current: str) -> list[Choice[str]]:
    """Suggest incomplete rescue tasks."""
    return [
        Choice(name=str(task), value=str(task))
        for task in RESCUE_SERVICE.rescues.search(current)[:5]
    ]


def _get_rescue(name: str) -> Rescue | None:
    """Get a active rescue from a display name."""
    search = re.search(r"<@(\d+?)>$", name)

    if not search:
        return None

    client_id = int(search.group(1))
    rescue = RESCUE_SERVICE.rescues.find(client=client_id)

    if not rescue:
        return None

    return rescue


class Slash(commands.GroupCog, group_name="rescue"):
    """Manually manage rescue tasks."""

    @app_commands.command(  # type: ignore [arg-type]
        name="rescuer",
        description="Modify a rescue task's rescuer.",
    )
    @app_commands.describe(
        task="Task to modify.",
        user="Rescuer in question.",
        state="State of assignment.",
    )
    @app_commands.choices(
        state=[
            Choice(name="Assigned", value=1),
            Choice(name="Unassigned", value=0),
        ],
    )
    async def rescuer(
        self,
        interaction: Interaction[Client],
        task: str,
        user: User,
        state: Choice[int],
    ) -> None:
        "Modify a rescue task's rescuer."
        await interaction.response.defer(ephemeral=True)

        missing = f"## :x: Bad Task :x:\nCould not find task: `{task}`\n"
        rescue = _get_rescue(task)

        if not rescue:
            await interaction.followup.send(missing, ephemeral=True)
            return

        await RESCUE_SERVICE.update_rescuer(rescue, user.id, bool(state.value))

        response = "## :tools: Rescuer Updated :tools:\n"
        await interaction.followup.send(response, ephemeral=True)

    @rescuer.autocomplete("task")
    async def rescuer_autocomplete(
        self, _: Interaction[Client], current: str
    ) -> list[Choice[str]]:
        """Generate suggestions for target tasks."""
        return _autocomplete(current)

    @app_commands.command(  # type: ignore [arg-type]
        name="close",
        description="Manually close a rescue task.",
    )
    @app_commands.describe(
        task="Task to close.",
        abort="Whether the task was successful.",
    )
    @app_commands.choices(
        abort=[
            Choice(name="True", value=1),
            Choice(name="False", value=0),
        ],
    )
    async def close(
        self,
        interaction: Interaction[Client],
        task: str,
        abort: Choice[int],
    ) -> None:
        """Manually close a rescue task."""
        await interaction.response.defer(ephemeral=True)

        missing = f"## :x: Bad Task :x:\nCould not find task: `{task}`\n"
        rescue = _get_rescue(task)

        if not rescue:
            await interaction.followup.send(missing, ephemeral=True)
            return

        await RESCUE_SERVICE.close_rescue(rescue.client, abort=bool(abort.value))

        response = "## :tools: Task Closed :tools:\n"
        await interaction.followup.send(response, ephemeral=True)

    @close.autocomplete("task")
    async def close_autocomplete(
        self,
        _: Interaction[Client],
        current: str,
    ) -> list[Choice[str]]:
        """Generate suggestions for target tasks."""
        return _autocomplete(current)


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(Slash(), DISCORD.test_guild_id)
