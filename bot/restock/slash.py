"""Manually manage restock tasks."""

from discord import Client, Interaction, User, app_commands
from discord.app_commands import Choice
from discord.ext import commands

from bot.core import CLIENT
from services.depots import DEPOT_SERVICE
from services.restocks import RESTOCK_SERVICE
from settings import DISCORD


def _autocomplete(current: str) -> list[Choice[str]]:
    """Suggest incomplete restock tasks."""
    return [
        Choice(name=str(task), value=str(task))
        for task in RESTOCK_SERVICE.restocks.search(current)[:5]
    ]


class Slash(commands.GroupCog, group_name="restock"):
    """Manually manage restock tasks."""

    @app_commands.command(  # type: ignore [arg-type]
        name="hauler",
        description="Modify a restock task's hauler.",
    )
    @app_commands.describe(
        task="Task to modify.",
        user="Hauler in question.",
        state="State of assignment.",
    )
    @app_commands.choices(
        state=[
            Choice(name="Assigned", value=1),
            Choice(name="Unassigned", value=0),
        ],
    )
    async def hauler(
        self,
        interaction: Interaction[Client],
        task: str,
        user: User,
        state: Choice[int],
    ) -> None:
        "Modify a restock task's hauler."
        await interaction.response.defer(ephemeral=True)

        if len(task) == 7:
            callsign = task.upper()
        else:
            callsign = task[1:8]

        restock = RESTOCK_SERVICE.restocks.find(callsign=callsign)

        if not restock:
            response = f"## :x: Bad Task :x:\nCould not find task: `{task}`\n"
            await interaction.followup.send(response, ephemeral=True)
            return

        await RESTOCK_SERVICE.update_hauler(restock, user.id, bool(state.value))

        response = "## :tools: Hauler Updated :tools:\n"
        await interaction.followup.send(response, ephemeral=True)

    @hauler.autocomplete("task")
    async def hauler_autocomplete(
        self, _: Interaction[Client], current: str
    ) -> list[Choice[str]]:
        """Generate suggestions for target tasks."""
        return _autocomplete(current)

    @app_commands.command(  # type: ignore [arg-type]
        name="close",
        description="Manually close a restock task.",
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
        """Manually close a restock task."""
        await interaction.response.defer(ephemeral=True)

        if len(task) == 7:
            callsign = task.upper()
        else:
            callsign = task[1:8]

        restock = RESTOCK_SERVICE.restocks.find(callsign=callsign)

        if not restock:
            response = f"## :x: Bad Task :x:\nCould not find task: `{task}`\n"
            await interaction.followup.send(response, ephemeral=True)
            return

        depot = DEPOT_SERVICE.carriers.find(callsign=restock.carrier[0])
        assert depot
        await RESTOCK_SERVICE.close_restock(depot, abort=bool(abort.value))

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
