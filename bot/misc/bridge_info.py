"""Gets information on the Colonia Bridge."""

import logging
from io import BytesIO
from typing import Any

from discord import Client, File, Interaction, app_commands
from discord.ext import commands

from bot.core import CLIENT
from services.depots import DEPOT_SERVICE
from settings import DISCORD
from utils import table

_LOGGER = logging.getLogger(__name__)
_LENGTH = 25


class BridgeInfo(commands.Cog):
    """Gets information on the Colonia Bridge."""

    @app_commands.command(  # type: ignore [arg-type]
        name="bridge",
        description="Get information on the Colonia bridge.",
    )
    @app_commands.describe(
        cutoff="Ignore stations with less tritium then this.",
    )
    async def bridge(
        self,
        interaction: Interaction[Client],
        cutoff: int | None = None,
    ) -> None:
        """Pretend a market update was sent."""
        await interaction.response.defer(ephemeral=True)

        if cutoff is None:
            cutoff = 0

        bridges = [
            x
            for x in DEPOT_SERVICE.bridges
            if x.tritium and x.tritium.stock.quantity >= cutoff
        ]
        # Sort the bridges (that have tritium) by their stock
        bridges = sorted(
            bridges,
            key=lambda x: x.tritium.stock.quantity,  # type: ignore [union-attr]
            reverse=True,
        )

        bridge_matrix: list[list[Any]] = [["Name", "System", "Stock", "Price"]]
        bridge_matrix += [
            [
                bridge.name,
                bridge.system.name,
                bridge.tritium.stock.quantity,
                bridge.tritium.stock.price,
            ]
            for bridge in bridges[:_LENGTH]
            if bridge.tritium
        ]
        table_str = table.pretty(bridge_matrix, ignore=["Name"])

        total_tritium = sum(
            bridge.tritium.stock.quantity for bridge in bridges if bridge.tritium
        )

        if len(bridges) > _LENGTH:
            table_str += f"\n({len(bridges)-_LENGTH} more bridges...)"

        with BytesIO(table_str.encode("utf-8")) as bytes_io:
            response = (
                "## :bridge_at_night: Colonia Bridge Info :bridge_at_night:\n"
                + f"Total tritum: **{total_tritium}**"
                + "\nStations matching search:"
            )

            file = File(bytes_io, "bridges.txt")
            await interaction.followup.send(response, ephemeral=True, file=file)

        _LOGGER.info("Send bridge info to %s", interaction.user.name)


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(BridgeInfo(), DISCORD.main_guild_id)
