"""Allow managing depot deployments."""

import logging

from discord import Client, File, Interaction, User, app_commands
from discord.app_commands import Choice, Range
from discord.ext import commands

from bot.core import CLIENT
from common.depots import Carrier
from external import edsm, inara, spansh
from services import CAPI_SERVICE, DEPOT_SERVICE, Colour, Galaxy
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
        reserve: int,
        capacity: int,
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


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(Deploy(), DISCORD.test_guild_id)
