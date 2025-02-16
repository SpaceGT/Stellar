"""Allow managing depot deployments."""

from discord import Client, File, Interaction, app_commands
from discord.ext import commands

from bot.core import CLIENT
from external import spansh
from services import DEPOT_SERVICE, Colour, Galaxy
from services.galaxy import Gradient
from settings import DISCORD
from utils.points import Point2D, Point3D

_CELL_SIZE = (5000, 5000)
_REGION_CENTER = Point2D(0, 26000)
_MAX_DISTANCE = 40000


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


def _get_most_isolated() -> Point2D:
    """Return the center point furthest away from all depots."""
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
        points.append((point, closest_depot_distance))

    return max(points, key=lambda x: x[1])[0]


class Deploy(commands.GroupCog, group_name="deploy"):
    """Allow managing depot deployments."""

    @app_commands.command(  # type: ignore [arg-type]
        name="view",
        description="View the next recommended deployment location.",
    )
    async def view(self, interaction: Interaction[Client]) -> None:
        "View the next recommended deployment cell."
        centers = [Point3D(center.x, 0, center.y) for center in _compute_centers()]
        target = _get_most_isolated()
        target = Point3D(target.x, 0, target.y)

        galaxy = Galaxy()
        galaxy.add_points(
            [
                depot.deploy_system.location
                for depot in DEPOT_SERVICE.carriers
                if depot.active_depot and depot.deploy_system.location
            ],
            Gradient.GREEN,
        )
        galaxy.add_point(target, Gradient.BLUE)
        galaxy.add_cells(centers, Colour.BLUE, _CELL_SIZE)

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

        await interaction.response.send_message(
            response, file=galaxy_map, ephemeral=True
        )


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(Deploy(), DISCORD.test_guild_id)
