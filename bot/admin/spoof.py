"""Mock certain events and reroute messages."""

import copy
from datetime import datetime, timezone
from enum import StrEnum

from discord import Client, Interaction, app_commands
from discord.app_commands import Choice
from discord.ext import commands

from bot.core import CLIENT
from common import Good
from common.depots import stock_bracket
from services import DEPOT_SERVICE
from settings import DISCORD


class _MarketChoice(StrEnum):
    BUYING = "Buying"
    SELLING = "Selling"


class Spoof(commands.GroupCog, group_name="spoof"):
    """Mock certain events and reroute messages."""

    @app_commands.command(  # type: ignore [arg-type]
        name="market",
        description="Pretend a market update was sent.",
    )
    @app_commands.describe(
        depot="Target carrier.",
        stock="Tritium in market.",
        price="Price of tritium.",
        market="State of the market order.",
    )
    @app_commands.choices(
        market=[
            Choice(name="Buying", value=_MarketChoice.BUYING),
            Choice(name="Selling", value=_MarketChoice.SELLING),
        ],
    )
    async def market(
        self,
        interaction: Interaction[Client],
        depot: str,
        stock: int,
        price: int,
        market: Choice[str],
    ) -> None:
        """Pretend a market update was sent."""
        await interaction.response.defer(ephemeral=True)

        if len(depot) == 7:
            callsign = depot.upper()
        else:
            callsign = depot[1:8]

        carrier = DEPOT_SERVICE.carriers.find(callsign=callsign)

        if not carrier:
            response = f"## :x: Bad Depot :x:\nCould not find depot: `{depot}`\n"
            await interaction.followup.send(response, ephemeral=True)
            return

        new_market = copy.copy(carrier.market)
        if carrier.tritium:
            new_market.remove(carrier.tritium)

        tritium_market_data = {
            "price": price,
            "quantity": stock,
            "bracket": stock_bracket(stock),
        }
        new_tritium = Good(
            "tritium",
            tritium_market_data if market.value == _MarketChoice.SELLING else {},
            tritium_market_data if market.value == _MarketChoice.BUYING else {},
        )

        new_market.append(new_tritium)

        await DEPOT_SERVICE.listener(
            carrier.name,
            carrier.system.name,
            new_market,
            carrier.market_id,
            datetime.now(timezone.utc),
        )

        response = (
            "## :incoming_envelope: Mocked Market Update :incoming_envelope:\n"
            + f"**Depot:**  `{depot}`\n"
            + f"**Tritium:**  `{stock:,}t`\n"
            + f"**{market.value.title()} Price:**  `{price:,}cr/t`\n\n"
        )

        await interaction.followup.send(response, ephemeral=True)

    @market.autocomplete("depot")
    async def depot_autocomplete(
        self,
        _: Interaction[Client],
        current: str,
    ) -> list[Choice[str]]:
        """Generate suggestions for target depots."""
        return [
            Choice(name=str(depot), value=str(depot))
            for depot in DEPOT_SERVICE.carriers.search(current)[:5]
        ]


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(Spoof(), DISCORD.test_guild_id)
