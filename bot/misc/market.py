"""Sync your carrier market with third party tools."""

import copy
import logging
import re
from enum import IntEnum

from discord import Client, Interaction, app_commands
from discord.app_commands import Choice
from discord.ext import commands
from thefuzz import process  # type: ignore [import-untyped]

from bot.core import CLIENT
from common import Good
from common.depots import stock_bracket
from external import eddn, edsm, inara
from services.depots import DEPOT_SERVICE
from settings import DISCORD

_LOGGER = logging.getLogger(__name__)


class _MarketChoice(IntEnum):
    BUYING = 1
    SELLING = 2


class _ServiceChoice(IntEnum):
    INARA = 1
    EDSM = 2
    SELF = 3
    NONE = 0


class Market(commands.Cog):
    """Sync your carrier market with third party tools."""

    @app_commands.command(  # type: ignore [arg-type]
        name="market",
        description="Sync your carrier market with third party tools.",
    )
    @app_commands.describe(
        tritium="Tritium in market.",
        price="Price of tritium.",
        market="State of the market order.",
        service="Fetch the rest of your market from this service.",
        carrier="Specify a depot if you own multiple.",
    )
    @app_commands.choices(
        market=[
            Choice(name="Buying", value=_MarketChoice.BUYING),
            Choice(name="Selling", value=_MarketChoice.SELLING),
        ],
        service=[
            Choice(name="INARA", value=_ServiceChoice.INARA),
            Choice(name="EDSM", value=_ServiceChoice.EDSM),
            Choice(name="Stellar", value=_ServiceChoice.SELF),
            Choice(name="None", value=_ServiceChoice.NONE),
        ],
    )
    async def market(
        self,
        interaction: Interaction[Client],
        tritium: int,
        price: int,
        market: Choice[int],
        service: Choice[int],
        carrier: str | None = None,
    ) -> None:
        """Sync your carrier market with third party tools."""
        await interaction.response.defer(ephemeral=True)

        assert interaction.client.application is not None
        is_owner = interaction.client.application.owner.id == interaction.user.id

        if carrier:
            if len(carrier) == 7:
                callsign = carrier.upper()
            else:
                callsign = carrier[1:8]

            depot = DEPOT_SERVICE.carriers.find(callsign=callsign)

            if not depot or (
                not is_owner and depot.owner_discord_id != interaction.user.id
            ):
                response = (
                    "## :mag: Cannot Access Depot :mag:\n"
                    + f"Ensure `{carrier}` exists and that you are the registered owner."
                )
                await interaction.followup.send(response, ephemeral=True)
                return

        else:
            depots = list(
                filter(
                    lambda x: x.owner_discord_id == interaction.user.id,
                    DEPOT_SERVICE.carriers,
                )
            )

            if len(depots) > 1:
                response = (
                    "## :mag: Ambiguous Depot :mag:\n"
                    + "You have multiple registered depots.\n"
                    + "Please specify which one you wish to update."
                )
                await interaction.followup.send(response, ephemeral=True)
                return

            if len(depots) == 0:
                response = (
                    "## :mag: Cannot Find Depot :mag:\n"
                    + "Ensure you have registered it with STAR!\n"
                    + f"<@{interaction.client.application.owner.id}> will be happy to assist you :)"
                )
                await interaction.followup.send(response, ephemeral=True)
                return

            depot = depots[0]

        new_market: list[Good]
        match service.value:
            case _ServiceChoice.EDSM:
                new_market = await edsm.market(depot.market_id)

            case _ServiceChoice.INARA:
                search = re.search(
                    r"^https:\/\/inara\.cz\/station\/(\d+)$", depot.inara_url
                )
                assert search
                inara_id = int(search.group(1))

                try:
                    new_market, _, _ = await inara.overview(inara_id)
                except ValueError:
                    _LOGGER.exception("Error when updating from INARA")
                    new_market = []

            case _ServiceChoice.SELF:
                new_market = copy.copy(depot.market)

            case _ServiceChoice.NONE:
                new_market = []

        # Ignore tritium currently in the market
        new_market = list(filter(lambda x: x.name != "tritium", new_market))

        tritium_market_data = {
            "price": price,
            "quantity": tritium,
            "bracket": stock_bracket(tritium),
        }
        new_tritium = Good(
            "tritium",
            tritium_market_data if market.value == _MarketChoice.SELLING else {},
            tritium_market_data if market.value == _MarketChoice.BUYING else {},
        )

        new_market.append(new_tritium)

        success = await eddn.upload.commodity(
            depot.name,
            depot.system.name,
            new_market,
            depot.market_id,
            str(interaction.user.id),
        )

        if not success:
            error_message = (
                "## :warning: EDDN Update Failed :warning:\n"
                + f"If this issue persists please ping <@{interaction.client.application.owner.id}>"
            )
            await interaction.followup.send(error_message, ephemeral=True)
            return

        response = (
            "## :incoming_envelope: EDDN Update Sent :incoming_envelope:\n"
            + f"**Depot:**  `{carrier}`\n"
            + f"**Tritium:**  `{tritium:,}t`\n"
            + f"**{market.name.removesuffix('ing')} Price:**  `{price:,}cr/t`\n\n"
        )

        if service.value == _ServiceChoice.NONE:
            response += "(All other market data has been overwritten)"
        else:
            preserved = len(new_market) - 1
            response += (
                f"(Preserved `{preserved}` other market "
                + f"order{'s' if preserved != 1 else ''} from `{service.name}`)"
            )

        await interaction.followup.send(response, ephemeral=True)

    @market.autocomplete("carrier")
    async def depot_autocomplete(
        self,
        interaction: Interaction[Client],
        current: str,
    ) -> list[Choice[str]]:
        """Generate suggestions for owned depots."""
        assert interaction.client.application is not None

        if interaction.client.application.owner.id == interaction.user.id:
            targets = list(DEPOT_SERVICE.carriers)
        else:
            targets = list(
                carrier
                for carrier in DEPOT_SERVICE.carriers
                if carrier.owner_discord_id == interaction.user.id
            )

        if current:
            targets = list(
                carrier
                for carrier, _ in process.extract(
                    current,
                    targets,
                    processor=str,
                    limit=len(targets),
                )
            )

        return [Choice(name=str(depot), value=str(depot)) for depot in targets[:5]]


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(Market(), DISCORD.main_guild_id)
