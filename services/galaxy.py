"""
View systems on a galaxy map.
Designed to work with https://www.edsm.net/img/galaxyBackgroundV2.jpg
"""

from enum import Enum
from io import BytesIO

from PIL import Image, ImageColor, ImageDraw

from settings import CONFIG_DIR
from utils.points import Point2D, Point3D


class Gradient(Enum):
    """Subtle colour gradients."""

    GREEN = ("#78CC78", "#53BE53")


class Colour(Enum):
    """Friendly colour names."""

    GREY = "#2C2C2C"


def _world_to_screen(point: Point2D) -> Point2D:
    """Converts a 2D Point in LY to a point on the map in pixels."""

    density = 9 * 10**-3  # Pixels per lightyear
    origin = (450, 683)  # Position of Sol

    x = int(density * point.x + origin[0])
    y = int(density * -point.y + origin[1])

    return Point2D(x, y)


def _gradient(
    size: tuple[int, int],
    start_colour: tuple[int, int, int, int],
    end_colour: tuple[int, int, int, int],
) -> Image.Image:
    """Create a linear gradient between two colours."""

    width = size[0]
    height = size[1]

    gradient = Image.new("RGBA", size)
    for y in range(height):
        ratio = y / height

        r = int(start_colour[0] + ratio * (end_colour[0] - start_colour[0]))
        g = int(start_colour[1] + ratio * (end_colour[1] - start_colour[1]))
        b = int(start_colour[2] + ratio * (end_colour[2] - start_colour[2]))
        a = int(start_colour[3] + ratio * (end_colour[3] - start_colour[3]))

        for x in range(width):
            gradient.putpixel((x, y), (r, g, b, a))

    return gradient


def _circle(
    diameter: int,
    border: int,
    start_colour: tuple[int, int, int],
    end_colour: tuple[int, int, int],
    border_colour: tuple[int, int, int, int],
) -> Image.Image:
    """Create a circle with a gradient, border and anti-aliasing."""

    scale_factor = 5
    size = diameter * scale_factor
    padding = border * scale_factor

    gradient_mask = Image.new("L", (size, size), "black")
    ImageDraw.Draw(gradient_mask).ellipse(
        (
            padding,
            padding,
            size - padding,
            size - padding,
        ),
        fill="white",
        width=0,
    )

    background = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(background).ellipse(
        (0, 0, size, size),
        fill=border_colour,
        width=0,
    )

    gradient = _gradient((size, size), start_colour + (255,), end_colour + (255,))
    ellipse = Image.composite(gradient, background, gradient_mask)

    return ellipse.resize((diameter, diameter), Image.Resampling.LANCZOS)


class Galaxy:
    """Helper for drawing to a galaxy map."""

    def __init__(self):
        self._image = Image.open(CONFIG_DIR / "galaxy.jpg")

    def add_point(
        self,
        point: Point3D,
        colour: Gradient = Gradient.GREEN,
        outline: Colour = Colour.GREY,
        dot_size: int = 26,
        border_size: int = 2,
    ) -> None:
        """Add a marker at a point on the galaxy."""

        dot_radius = dot_size // 2
        image_point = _world_to_screen(Point2D(point.x, point.z))

        start_colour = ImageColor.getcolor(colour.value[0], "RGB")
        end_colour = ImageColor.getcolor(colour.value[1], "RGB")
        border_colour = ImageColor.getcolor(outline.value, "RGB") + (250,)

        assert len(start_colour) == 3
        assert len(end_colour) == 3
        assert len(border_colour) == 4

        ellipse = _circle(
            dot_size, border_size, start_colour, end_colour, border_colour
        )

        self._image.paste(
            ellipse,
            (
                image_point.x - dot_radius,
                image_point.y - dot_radius,
                image_point.x + dot_radius,
                image_point.y + dot_radius,
            ),
            ellipse,
        )

    def view(self) -> None:
        """Display the image."""
        self._image.show()

    def render(self) -> BytesIO:
        """Save the image into a bytes object."""
        img_bytes = BytesIO()
        self._image.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return img_bytes
