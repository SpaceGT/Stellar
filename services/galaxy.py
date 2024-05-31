"""
View systems on a galaxy map.
Designed to work with https://www.edsm.net/img/galaxyBackgroundV2.jpg
"""

import logging
from io import BytesIO

from PIL import Image, ImageDraw

from settings import CONFIG_DIR
from utils.points import Point2D, Point3D

_LOGGER = logging.getLogger(__name__)


def _map_point_to_image(point: Point2D) -> Point2D:
    """Converts a 2D Point in LY to a point on the map in pixels."""

    density = 9 * 10**-3  # Lightyears per pixel
    origin = (450, 683)  # Position of Sol

    x = density * point.x + origin[0]
    y = density * -point.y + origin[1]

    return Point2D(x, y)


def render(
    points: list[Point3D],
    size: int = 26,
    colour: str = "#64C564",
) -> BytesIO:
    """Render points on the galaxy map."""

    point_radius = size // 2
    top_down_points = (Point2D(point.x, point.z) for point in points)

    with Image.open(CONFIG_DIR / "galaxy.jpg") as img:
        draw = ImageDraw.Draw(img)

        for point in top_down_points:
            image_point = _map_point_to_image(point)

            draw.ellipse(
                [
                    (image_point.x - point_radius, image_point.y - point_radius),
                    (image_point.x + point_radius, image_point.y + point_radius),
                ],
                fill=colour,
                outline=None,
            )

        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        _LOGGER.debug("Created galaxy image for %s", ",".join(map(str, points)))

        return img_bytes
