"""Present various information about the initiative."""

import logging
from datetime import timedelta
from typing import Any

from discord import Client, Interaction, Member, app_commands
from discord.app_commands import Choice
from discord.ext import commands

from bot.core import CLIENT
from common.tasks import Restock
from services.depots import DEPOT_SERVICE
from services.rescues import RESCUE_SERVICE
from services.restocks import RESTOCK_SERVICE
from settings import DISCORD

_LOGGER = logging.getLogger(__name__)
_LEADER_BOARD_LENGTH = 5
_MENTION_LENGTH = 10


class Stats(commands.GroupCog, group_name="statistics"):
    """Present various information about the initiative."""

    @staticmethod
    def _ordinal(number: int) -> str:
        return str(number) + (
            "th"
            if 4 <= number % 100 <= 20
            else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
        )

    def _search_restocks(self, user_id: int) -> list[Restock]:
        restocks = [
            restock
            for restock in RESTOCK_SERVICE.restocks
            if user_id in restock.haulers
        ]
        return restocks

    def _restock_leaderboard(self) -> list[tuple[int, int]]:
        hits: dict[int, int] = {}

        for restock in RESTOCK_SERVICE.restocks:
            for hauler in restock.haulers:
                hits[hauler] = hits.get(hauler, 0) + 1

        items = list(hits.items())
        output = sorted(items, key=lambda x: (-x[1], x[0]))
        return output

    def _search_rescues(self, user_id: int) -> list[Any]:
        rescues = [
            rescue for rescue in RESCUE_SERVICE.rescues if user_id in rescue.rescuers
        ]
        return rescues

    def _rescue_leaderboard(self) -> list[tuple[int, int]]:
        hits: dict[int, int] = {}

        for rescue in RESCUE_SERVICE.rescues:
            for rescuer in rescue.rescuers:
                hits[rescuer] = hits.get(rescuer, 0) + 1

        items = list(hits.items())
        output = sorted(items, key=lambda x: (-x[1], x[0]))
        return output

    @app_commands.command(  # type: ignore [arg-type]
        name="user",
        description="Get statistics for a specific user.",
    )
    @app_commands.describe(user="User to fetch statistics on.")
    async def user(
        self,
        interaction: Interaction[Client],
        user: Member,
    ) -> None:
        "Get statistics for a specific user."
        depots = list(
            filter(lambda x: x.owner_discord_id == user.id, DEPOT_SERVICE.carriers)
        )

        main_guild = interaction.client.get_guild(DISCORD.main_guild_id)
        assert main_guild is not None
        roles = list(
            filter(
                None,
                (
                    user.get_role(role_id)
                    for role_id in [
                        DISCORD.hauler_role_id,
                        DISCORD.rescue_role_id,
                        DISCORD.depot_role_id,
                    ]
                ),
            )
        )

        response = f"## :mag: User Statistics :mag:\n{user.mention}"

        if roles:
            response += f" ({' '.join([role.mention for role in roles])})\n"
        else:
            response += "\n"

        rescues = self._search_rescues(user.id)
        if rescues:
            position = self._rescue_leaderboard().index((user.id, len(rescues))) + 1
            rank = (
                f"  ({Stats._ordinal(position)})" if position <= _MENTION_LENGTH else ""
            )
            response += f"**Rescues:**  `{len(rescues)}`{rank}\n"

        restocks = self._search_restocks(user.id)
        if restocks:
            position = self._restock_leaderboard().index((user.id, len(restocks))) + 1
            rank = (
                f"  ({Stats._ordinal(position)})" if position <= _MENTION_LENGTH else ""
            )
            response += f"**Refills:**  `{len(restocks)}`{rank}\n"

        if depots:
            active = []
            inactive = []

            for depot in depots:
                if depot.active_depot:
                    active.append(f"`{depot}`")
                else:
                    inactive.append(f"`{depot}`")

            # Single depot accounts
            if len(active + inactive) == 1:
                response += f"**Depot:**  {(active + inactive)[0]}"
                if inactive:
                    response += " (Delisted)"

            # Multi depot accounts
            else:
                if active:
                    if inactive:
                        response += "\n**Active Depots:**\n"
                    else:
                        response += "\n**Depots:**\n"

                    response += "\n".join(active) + "\n"

                if inactive:
                    response += "\n**Delisted Depots:**\n"
                    response += "\n".join(inactive) + "\n"

        _LOGGER.info("Got stats on %s for %s", user.name, interaction.user.name)

        if not any((roles, rescues, rescues, depots)):
            response = (
                "## :mag: User Statistics :mag:\n"
                + f"{user.mention} has not contributed."
            )

        await interaction.response.send_message(response, ephemeral=True)

    @app_commands.command(  # type: ignore [arg-type]
        name="depot",
        description="Get statistics for a specific depot.",
    )
    @app_commands.describe(depot="Depot to fetch statistics on.")
    async def depot(
        self,
        interaction: Interaction[Client],
        depot: str,
    ) -> None:
        "Get statistics for a specific depot."

        if len(depot) == 7:
            callsign = depot.upper()
        else:
            callsign = depot[1:8]

        carrier = DEPOT_SERVICE.carriers.find(callsign=callsign)

        if carrier is None:
            response = f"## :x: Bad Depot :x:\nCould not find depot: `{depot}`\n"
            await interaction.response.send_message(response, ephemeral=True)
            return

        response = (
            "# :mag: Depot Statistics :mag:\n"
            + "## Core :construction_site:\n"
            + f"**Depot:**  `[{carrier.name}] {carrier.display_name}`\n"
            + f"**System:**  `{carrier.system}`\n"
            + f"**Owner:**  <@{carrier.owner_discord_id}>\n"
            + f"**Update:**  <t:{int(carrier.last_update.timestamp())}:R>\n"
        )

        if carrier.tritium:
            if carrier.tritium.demand.quantity > 0:
                good = carrier.tritium.demand
                market = "Buying"
            else:
                good = carrier.tritium.stock
                market = "Selling"

            response += (
                "## Market :chart_with_upwards_trend:\n"
                + f"**Tritium:**  `{good.quantity:,}t`\n"
                + f"**Price:**  `{good.price:,}cr/t`\n"
                + f"**Market:**  `{market}`\n"
            )
        else:
            response += "**Market:** `Not Stocked`\n"

        response += (
            "## Technical :robot:\n"
            + f"**Identifier:**  `{carrier.market_id}`\n"
            + f"**Reserve:**  `{carrier.reserve_tritium:,}t`\n"
            + f"**Allocated:**  `{carrier.allocated_space:,}t`\n"
            + f"**Syncing:**  `{carrier.inara_poll}`\n"
        )

        restocks = sorted(
            [
                restock
                for restock in RESTOCK_SERVICE.restocks
                if carrier.name in restock.carrier[0]
            ],
            key=lambda task: task.progress.start,
        )

        if len(restocks) >= 2:
            intervals = [
                next.progress.start - current.progress.end
                for current, next in zip(restocks, restocks[1:])
                if next.progress.start and current.progress.end
            ]
            average = sum(intervals, timedelta()) / len(intervals)

            response += (
                "## Refills :ship:\n"
                + f"**Number:**  `{len(restocks):,}`\n"
                + f"**Tonnage:**  `{sum(restock.tritium.delivered for restock in restocks):,}t`\n"
                + f"**Interval:**  `{average.days:,} days`\n"
            )

        _LOGGER.info("Got statistics on '%s' for %s", depot, interaction.user.name)

        await interaction.response.send_message(response, ephemeral=True)

    @depot.autocomplete("depot")
    async def depot_autocomplete(
        self, _: Interaction[Client], current: str
    ) -> list[Choice[str]]:
        """Generate suggestions for target depots."""
        return [
            Choice(name=str(depot), value=str(depot))
            for depot in DEPOT_SERVICE.carriers.search(current)[:5]
        ]

    @app_commands.command(  # type: ignore [arg-type]
        name="overview",
        description="Get general statistics on the initiative.",
    )
    async def overiew(
        self,
        interaction: Interaction[Client],
    ) -> None:
        "Get general statistics on the initiative."
        response = "# :mag: General Statistics :mag:\n"

        restocks = sorted(
            RESTOCK_SERVICE.restocks,
            key=lambda task: task.progress.start,
        )
        if len(restocks) >= 2:
            intervals = [
                next.progress.start - current.progress.start
                for current, next in zip(restocks, restocks[1:])
            ]
            average = sum(intervals, timedelta()) / len(intervals)

            response += (
                "## Refills :ship:\n"
                + f"**Number:**  `{len(restocks):,}`\n"
                + f"**Tonnage:**  `{sum(restock.tritium.delivered for restock in restocks):,}t`\n"
                + f"**Interval:**  `{average.days:,} days`\n"
            )

        rescues = sorted(
            RESCUE_SERVICE.rescues,
            key=lambda task: task.progress.start,
        )
        if len(rescues) >= 2:
            intervals = [
                next.progress.start - current.progress.start
                for current, next in zip(rescues, rescues[1:])
            ]
            average = sum(intervals, timedelta()) / len(intervals)

            response += (
                "## Rescues :helicopter:\n"
                + f"**Number:**  `{len(rescues):,}`\n"
                + f"**Interval:**  `{average.days:,} days`\n"
            )

        response += (
            "# :champagne_glass: Leaderboards :champagne_glass:\n"
            + "## Tankers :truck:\n"
            + "".join(
                [
                    f"{rank+1}) <@{user_id}> - `{number}`\n"
                    for rank, (user_id, number) in enumerate(
                        self._restock_leaderboard()[:_LEADER_BOARD_LENGTH]
                    )
                ]
            )
            + "## Rescuers :ambulance:\n"
            + "".join(
                [
                    f"{rank+1}) <@{user_id}> - `{number}`\n"
                    for rank, (user_id, number) in enumerate(
                        self._rescue_leaderboard()[:_LEADER_BOARD_LENGTH]
                    )
                ]
            )
        )

        _LOGGER.info("Got general statistics for %s", interaction.user.name)

        await interaction.response.send_message(response, ephemeral=True)


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(Stats(), DISCORD.main_guild_id)
