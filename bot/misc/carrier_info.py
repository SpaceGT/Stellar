"""Display the carriers nearest to a system of choice."""

import asyncio
import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from discord import Client, File, Interaction, app_commands
from discord.app_commands import Choice
from discord.ext import commands

from bot.core import CLIENT
from external import edsm, spansh
from services.depots import DEPOT_SERVICE
from settings import DISCORD
from utils import table

_LOGGER = logging.getLogger(__name__)
_LENGTH = 20


class CarrierInfo(commands.Cog):
    """Display the carriers nearest to a system of choice."""

    @app_commands.command(  # type: ignore [arg-type]
        name="depots",
        description="Show depots nearest to a system of choice.",
    )
    @app_commands.describe(
        system="Find depots closest to this system.",
        distance="Ignore depots further away then this.",
    )
    async def depots(
        self, interaction: Interaction[Client], system: str, distance: int
    ) -> None:
        """Show depots nearest to a system of choice."""
        system_info = await edsm.system(system)

        if system_info is None:
            response = (
                f"## :x: Bad System :x:\nThe system `{system}` was not recognised!\n"
            )
            await interaction.response.send_message(response, ephemeral=True)
            return

        point = system_info.location

        carriers = [
            carrier
            for carrier in DEPOT_SERVICE.carriers
            if carrier.tritium
            and carrier.active_depot
            and carrier.tritium.stock.quantity > 0
            and carrier.deploy_system.name == carrier.system.name
            and carrier.deploy_system.location.distance(point) <= distance
        ]
        carriers = sorted(
            carriers, key=lambda x: x.deploy_system.location.distance(point)
        )

        carrier_matrix: list[list[Any]] = [
            ["Callsign", "Name", "System", "Distance", "Stock", "Price", "Update"]
        ]
        carrier_matrix += [
            [
                carrier.name,
                carrier.display_name,
                carrier.system.name,
                round(carrier.deploy_system.location.distance(point)),
                carrier.tritium.stock.quantity,  # type: ignore [union-attr]
                carrier.tritium.stock.price,  # type: ignore [union-attr]
                datetime.now(timezone.utc) - carrier.last_update,
            ]
            for carrier in carriers[:_LENGTH]
        ]
        table_str = table.pretty(carrier_matrix, ignore=["Callsign", "Name"])

        if len(carriers) > _LENGTH:
            table_str += f"\n({len(carriers)-_LENGTH} more depots...)"

        with BytesIO(table_str.encode("utf-8")) as bytes_io:
            response = "## :ship: Nearby Depots :ship:"

            file = File(bytes_io, "depots.txt")
            await interaction.response.send_message(response, ephemeral=True, file=file)

        _LOGGER.info("Send carrier info to %s", interaction.user.name)

    @depots.autocomplete("system")
    async def system_autocomplete(
        self,
        _: Interaction[Client],
        current: str,
    ) -> list[Choice[str]]:
        """Generate suggestions for target systems."""
        if not current:
            return []

        choices: list[Choice[str]] = []

        try:
            systems = await asyncio.wait_for(spansh.predict_system(current), timeout=3)
        except TimeoutError:
            _LOGGER.warning("Could not find system suggestions for '%s'", current)
        else:
            choices = [
                Choice(name=str(system), value=str(system)) for system in systems[:5]
            ]

        return choices


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(CarrierInfo(), DISCORD.main_guild_id)
