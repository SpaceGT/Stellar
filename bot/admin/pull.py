"""Allow for manually syncing depots."""

from io import BytesIO

from discord import Client, File, Interaction, app_commands
from discord.ext import commands

from bot.core import CLIENT
from services import DEPOT_SERVICE
from settings import DISCORD


class Pull(commands.GroupCog, group_name="pull"):
    """Allow for manually syncing depots."""

    @app_commands.command(  # type: ignore [arg-type]
        name="depots",
        description="Gets the latest list of depots from the Google Sheet.",
    )
    async def depots(self, interaction: Interaction[Client]) -> None:
        """Gets the latest list of depots from the Google Sheet."""

        await interaction.response.defer(ephemeral=True)
        await DEPOT_SERVICE.pull()
        await DEPOT_SERVICE.verify()

        response = (
            "## :cloud: Pull Complete :cloud:\n"
            + f"Syncronzed `{len(DEPOT_SERVICE.depots)}` depots:\n"
        )

        depots = "\n".join(map(str, DEPOT_SERVICE.depots)).encode("utf-8")
        with BytesIO(depots) as bytes_io:
            await interaction.followup.send(
                response, ephemeral=True, file=File(bytes_io, "depots.txt")
            )

    @app_commands.command(  # type: ignore [arg-type]
        name="markets",
        description="Gets the latest depot market data from EDSM.",
    )
    async def market(self, interaction: Interaction[Client]) -> None:
        """Gets the latest depot market data from EDSM."""

        await interaction.response.defer(ephemeral=True)
        await DEPOT_SERVICE.edsm_update()

        orders = sum(len(depot.market) for depot in DEPOT_SERVICE.depots)

        response = (
            "## :cloud: Update Complete :cloud:\n"
            + f"Updated `{orders}` orders from EDSM."
        )

        await interaction.followup.send(response, ephemeral=True)


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(Pull(), DISCORD.test_guild_id)
