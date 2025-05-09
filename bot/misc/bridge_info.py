"""Gets information on the Colonia Bridge."""

import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from discord import Client, File, Interaction, app_commands
from discord.ext import commands

from bot.core import CLIENT
from services import DEPOT_SERVICE
from settings import DISCORD
from utils import table

_LOGGER = logging.getLogger(__name__)
_LENGTH = 20


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

        bridge_matrix: list[list[Any]] = [
            ["Name", "System", "Stock", "Price", "Update"]
        ]
        bridge_matrix += [
            [
                bridge.name,
                bridge.system.name,
                bridge.tritium.stock.quantity,
                bridge.tritium.stock.price,
                datetime.now(timezone.utc) - bridge.last_update,
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
            await interaction.response.send_message(response, ephemeral=True, file=file)

        _LOGGER.info("Send bridge info to %s", interaction.user.name)


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(BridgeInfo(), DISCORD.main_guild_id)
