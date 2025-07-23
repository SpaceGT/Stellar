"""Allow managing depot deployments."""

import asyncio
import logging

from discord import Client, File, Interaction, User, app_commands
from discord.app_commands import Choice, Range
from discord.ext import commands

from bot.core import CLIENT
from common import Good, System
from common.depots import CAPACITY, Carrier
from common.enums import State
from external import edsm, inara, spansh
from external.capi import CapiAuthFail, CapiQueryFail, EpicFail, NewTokenFail
from services import CAPI_SERVICE, DEPOT_SERVICE, Colour, Galaxy
from services.capi.utils import sync_carrier
from services.galaxy import Gradient
from settings import DISCORD
from utils.points import Point2D, Point3D

_CELL_SIZE = (5000, 5000)
_REGION_CENTER = Point2D(0, 26000)
_MAX_DISTANCE = 40000

_LOGGER = logging.getLogger(__name__)


def _compute_centers(
    origin: Point2D = _REGION_CENTER,
    distance: int = _MAX_DISTANCE,
    size: tuple[int, int] = _CELL_SIZE,
) -> list[Point2D]:
    """Return the centers of every valid cell."""
    points: list[Point2D] = []

    for x in range(-distance, distance + size[0], size[0]):
        for y in range(-distance, distance + size[1], size[1]):
            point = Point2D(x, y)

            if point.magnitude <= distance:
                points.append(point + origin)

    return points


def _get_most_isolated(depot_locations: list[Point3D] | None = None) -> Point2D:
    """
    Return the center point furthest away from all depots.
    Optionally accepts additional depot locations.
    """
    points: list[tuple[Point2D, float]] = []

    for point in _compute_centers():
        closest_depot_distance = min(
            Point2D(
                x=depot.deploy_system.location.x,
                y=depot.deploy_system.location.z,
            ).distance(point)
            for depot in DEPOT_SERVICE.carriers
            if depot.active_depot and depot.deploy_system.location
        )

        if depot_locations:
            closest_depot_distance = min(
                closest_depot_distance,
                min(
                    Point2D(
                        x=location.x,
                        y=location.z,
                    ).distance(point)
                    for location in depot_locations
                ),
            )

        points.append((point, closest_depot_distance))

    return max(points, key=lambda x: x[1])[0]


class Deploy(commands.GroupCog, group_name="deploy"):
    """Allow managing depot deployments."""

    @app_commands.command(  # type: ignore [arg-type]
        name="view",
        description="View the next recommended deployment location.",
    )
    @app_commands.describe(
        levels="Assume the first n locations are occupied.",
    )
    async def view(
        self,
        interaction: Interaction[Client],
        levels: Range[int, 0, 99] | None = None,
    ) -> None:
        "View the next recommended deployment cell."
        await interaction.response.defer(ephemeral=True)
        centers = [Point3D(center.x, 0, center.y) for center in _compute_centers()]

        galaxy = Galaxy()
        galaxy.add_cells(centers, Colour.BLUE, _CELL_SIZE)
        galaxy.add_points(
            [
                depot.deploy_system.location
                for depot in DEPOT_SERVICE.carriers
                if depot.active_depot and depot.deploy_system.location
            ],
            Gradient.GREEN,
        )

        target: Point3D | Point2D | None = None
        previous: list[Point3D] = []
        levels = levels or 0

        for _ in range(levels + 1):
            target = _get_most_isolated(previous)
            target = Point3D(target.x, 0, target.y)

            if len(previous) < levels:
                colour = Gradient.RED
                previous.append(target)
            else:
                colour = Gradient.BLUE

            galaxy.add_point(target, colour)

        assert isinstance(target, Point3D)
        with galaxy.render() as gal_map:
            galaxy_map = File(gal_map, filename="image.png")

        nearest = await spansh.nearest_system(target)
        assert nearest.location
        distance = target.distance(nearest.location)

        response = (
            "# :map: Deployments :map:\n"
            + f"**Location:**  `({target.x:.0f}, {target.y:.0f}, {target.z:.0f})`\n"
            + f"**Nearest:**  `{nearest.name}`"
        )

        if distance > min(_CELL_SIZE):
            response += f" (`{distance:.0f}ly`!)"
        else:
            response += f" (`{distance:.0f}ly`)"

        await interaction.followup.send(response, file=galaxy_map, ephemeral=True)

        _LOGGER.info("Created deployment map for %s", interaction.user.name)

    @app_commands.command(  # type: ignore [arg-type]
        name="add",
        description="Register a new depot.",
    )
    @app_commands.describe(
        callsign="Callsign of depot.",
        owner="Owner of depot.",
        system="Deploy system.",
        reserve="Minimum tritium before refuel.",
        capacity="Maximum tritium capacity.",
        state="Status of depot.",
    )
    @app_commands.choices(
        state=[
            Choice(name="Active", value=1),
            Choice(name="Inactive", value=0),
        ],
    )
    async def add(
        self,
        interaction: Interaction[Client],
        callsign: str,
        owner: User,
        system: str,
        reserve: Range[int, 0, CAPACITY - 1],
        capacity: Range[int, 1, CAPACITY],
        state: Choice[int],
    ) -> None:
        """Register a new depot."""
        await interaction.response.defer(ephemeral=True)

        depot = DEPOT_SERVICE.carriers.find(callsign)
        if depot:
            response = f"## :x: Duplicate Depot :x:\n`{depot}` is already registered with STAR.\n"
            await interaction.followup.send(response, ephemeral=True)
            return

        deploy_system = await edsm.system(system)
        if not deploy_system:
            response = f"## :x: Missing System :x:\nSystem `{system}` is not on EDSM.\n"
            await interaction.followup.send(response, ephemeral=True)
            return

        data = await inara.search(callsign)
        if not data:
            response = f"## :x: Bad Depot :x:\nCould not find depot: `{callsign}`\n"
            await interaction.followup.send(response, ephemeral=True)
            return

        name, current_system_name, inara_id = data
        current_system = await edsm.system(current_system_name)

        if not current_system:
            response = f"## :x: Missing System :x:\nSystem `{current_system}` is not on EDSM.\n"
            await interaction.followup.send(response, ephemeral=True)
            return

        market_id = await edsm.market_id(callsign, current_system.name)
        if not market_id:
            response = f"## :x: Missing Depot :x:\nDepot `[{callsign}] {name}` is not on EDSM.\n"
            await interaction.followup.send(response, ephemeral=True)
            return

        market, current_system, update = await edsm.overview(market_id, timestamp=True)
        assert update
        carrier = Carrier(
            name=callsign,
            system=current_system,
            market=market,
            market_id=market_id,
            inara_url=f"https://inara.cz/station/{inara_id}",
            last_update=update,
            display_name=name,
            deploy_system=deploy_system,
            reserve_tritium=reserve,
            allocated_space=capacity,
            owner_discord_id=owner.id,
            active_depot=bool(state.value),
            capi_status=CAPI_SERVICE.get_state(callsign),
            restock_status=None,
        )

        DEPOT_SERVICE.carriers.add(carrier)
        await DEPOT_SERVICE.push()

        response = (
            "# :passport_control: Registration :passport_control:\n"
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
            + f"**Syncing:**  `{CAPI_SERVICE.get_state(carrier.name)}`\n"
        )

        await interaction.followup.send(response, ephemeral=True)
        _LOGGER.info("'%s' has been enlisted for '%s'", carrier, deploy_system)

    @app_commands.command(  # type: ignore [arg-type]
        name="update",
        description="Update an existing depot.",
    )
    @app_commands.describe(
        depot="Depot to update.",
        state="Status of depot.",
        market="Fetch market information from CAPI",
        system="Deploy system.",
        reserve="Minimum tritium before refuel.",
        capacity="Maximum tritium capacity.",
        owner="Owner of depot.",
        name="Name of depot.",
    )
    @app_commands.choices(
        state=[
            Choice(name="Active", value=1),
            Choice(name="Inactive", value=0),
        ],
        market=[
            Choice(name="Yes", value=1),
            Choice(name="No", value=0),
        ],
    )
    async def update(
        self,
        interaction: Interaction[Client],
        depot: str,
        state: Choice[int] | None,
        market: Choice[int] | None,
        system: str | None,
        reserve: Range[int, 0, CAPACITY - 1] | None,
        capacity: Range[int, 1, CAPACITY] | None,
        owner: User | None,
        name: str | None,
    ) -> None:
        """Update an existing depot."""
        await interaction.response.defer(ephemeral=True)

        if len(depot) == 7:
            callsign = depot.upper()
        else:
            callsign = depot[1:8]

        carrier = DEPOT_SERVICE.carriers.find(callsign=callsign)

        # Apply update atomically
        if carrier is None:
            response = f"## :x: Bad Depot :x:\nCould not find depot: `{depot}`"
            await interaction.followup.send(response, ephemeral=True)
            return

        if not any((state, market, system, reserve, capacity, owner, name)):
            response = f"## :x: Bad Update :x:\nPlease specify what you want to update."
            await interaction.followup.send(response, ephemeral=True)
            return

        deploy_system: System | None = None
        if system is not None:
            deploy_system = await edsm.system(system)
            if not deploy_system:
                response = (
                    f"## :x: Missing System :x:\nSystem `{system}` is not on EDSM."
                )
                await interaction.followup.send(response, ephemeral=True)
                return

        capi_response: tuple[tuple[str, str, int], list[Good], str] | None = None
        if market is not None and bool(market.value):
            carrier.capi_status = CAPI_SERVICE.get_state(carrier.name)

            if carrier.capi_status == State.UNLISTED:
                response = f"## :x: CAPI Fail :x:\nCarrier is not registered with CAPI."
                await interaction.followup.send(response, ephemeral=True)
                return

            if carrier.capi_status == State.EXPIRED:
                response = f"## :x: CAPI Fail :x:\nCould not refresh access token."
                await interaction.followup.send(response, ephemeral=True)
                return

            try:
                capi_response = await CAPI_SERVICE.fleetcarrier(carrier.name)
            except (EpicFail, CapiQueryFail, CapiAuthFail, NewTokenFail) as error:
                if isinstance(error, EpicFail):
                    response = (
                        f"## :x: CAPI Fail :x:\nFailed to authenticate with Epic."
                    )
                elif isinstance(error, (CapiQueryFail, CapiAuthFail)):
                    response = f"## :x: CAPI Fail :x:\nAn internal CAPI error occured."
                else:
                    response = f"## :x: CAPI Fail :x:\nCould not refresh access token."

                await interaction.followup.send(response, ephemeral=True)
                return

            if capi_response is None:
                response = f"## :x: Depot Decommissioned :x:\nDisabling `{carrier}` since it no longer exists."
                await interaction.followup.send(response, ephemeral=True)

                _LOGGER.warning("Disabling '%s' as it no longer exists.", str(carrier))
                carrier.active_depot = False

                await DEPOT_SERVICE.push()
                return

        # Update values after checks
        _LOGGER.info("Editing '%s' for %s", str(carrier), interaction.user.name)
        response = "## :clipboard: Depot Edited :clipboard:\n"

        if deploy_system is not None:
            response += (
                f"**Deploy System:**  `{carrier.deploy_system}` -> `{deploy_system}`\n"
            )
            _LOGGER.info(
                "Deploy System: '%s' -> '%s'", carrier.deploy_system, deploy_system
            )
            carrier.deploy_system = deploy_system

        if state is not None:
            response += f"**Active:**  `{str(carrier.active_depot).title()}` -> `{str(bool(state.value)).title()}`\n"
            _LOGGER.info(
                "Active: '%s' -> '%s'",
                str(carrier.active_depot).title(),
                str(bool(state.value)).title(),
            )
            carrier.active_depot = bool(state.value)

        if reserve is not None:
            response += (
                f"**Reserve:**  `{carrier.reserve_tritium:,}` -> `{reserve:,}`\n"
            )
            _LOGGER.info(
                "Reserve Tritium: '%s' -> '%s'", carrier.reserve_tritium, reserve
            )
            carrier.reserve_tritium = reserve

        if capacity is not None:
            response += (
                f"**Capacity:**  `{carrier.allocated_space:,}` -> `{capacity:,}`\n"
            )
            _LOGGER.info(
                "Allocated Space: '%s' -> '%s'", carrier.allocated_space, capacity
            )
            carrier.allocated_space = capacity

        if owner is not None:
            response += f"**Owner:**  <@{carrier.owner_discord_id}> -> <@{owner.id}>\n"
            _LOGGER.info(
                "Owner Discord Id: '%s' -> '%s'", carrier.owner_discord_id, owner.id
            )
            carrier.owner_discord_id = owner.id

        if name is not None:
            response += f"**Name:**  `[{carrier.name}] {carrier.display_name}` -> `[{carrier.name}] {name}`\n"
            _LOGGER.info(
                "Display Name: '[%s] %s' -> '[%s] %s'",
                carrier.name,
                carrier.display_name,
                carrier.name,
                name,
            )
            carrier.display_name = name

        if capi_response is not None:
            response += f"(Selling `{len(capi_response[1])}` commodities in `{capi_response[2]}`)\n"
            _LOGGER.info("Fetched %s commodities from CAPI", len(capi_response[1]))
            await sync_carrier(
                name=(capi_response[0][0], capi_response[0][1]),
                market_id=capi_response[0][2],
                market=capi_response[1],
                system=capi_response[2],
            )

        await DEPOT_SERVICE.push()
        await interaction.followup.send(response, ephemeral=True)

    @add.autocomplete("system")
    @update.autocomplete("system")
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

    @update.autocomplete("depot")
    async def depot_autocomplete(
        self, _: Interaction[Client], current: str
    ) -> list[Choice[str]]:
        """Generate suggestions for target depots."""
        return [
            Choice(name=str(depot), value=str(depot))
            for depot in DEPOT_SERVICE.carriers.search(current, inactive=True)[:5]
        ]


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(Deploy(), DISCORD.test_guild_id)
