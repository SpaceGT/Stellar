"""
View systems on a galaxy map.
Designed to work with https://www.edsm.net/img/galaxyBackgroundV2.jpg
"""

from enum import Enum
from io import BytesIO

from PIL import Image, ImageColor, ImageDraw

from settings import CONFIG_DIR
from utils.points import Point2D, Point3D

_PIXELS_PER_LIGHTYEAR = 9 * 10**-3


class Gradient(Enum):
    """Subtle colour gradients."""

    GREEN = ("#78CC78", "#53BE53")
    BLUE = ("#02ADFC", "#02D6FC")
    RED = ("#F44343", "#F33939")


class Colour(Enum):
    """Friendly colour names."""

    BLUE = "#02ADFC"
    GREY = "#2C2C2C"


def _world_to_screen(point: Point2D) -> Point2D:
    """Converts a 2D Point in LY to a point on the map in pixels."""
    origin = (450, 683)  # Position of Sol

    x = round(_PIXELS_PER_LIGHTYEAR * point.x + origin[0])
    y = round(_PIXELS_PER_LIGHTYEAR * -point.y + origin[1])

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
        self.add_points([point], colour, outline, dot_size, border_size)

    def add_points(
        self,
        points: list[Point3D],
        colour: Gradient = Gradient.GREEN,
        outline: Colour = Colour.GREY,
        dot_size: int = 26,
        border_size: int = 2,
    ) -> None:
        """Add markers for a list of points on the galaxy."""
        dot_radius = dot_size // 2

        start_colour = ImageColor.getcolor(colour.value[0], "RGB")
        end_colour = ImageColor.getcolor(colour.value[1], "RGB")
        border_colour = ImageColor.getcolor(outline.value, "RGB") + (250,)

        assert len(start_colour) == 3
        assert len(end_colour) == 3
        assert len(border_colour) == 4

        ellipse = _circle(
            dot_size, border_size, start_colour, end_colour, border_colour
        )

        for point in points:
            image_point = _world_to_screen(Point2D(point.x, point.z))
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

    def add_cells(
        self,
        points: list[Point3D],
        colour: Colour,
        size: tuple[int, int],
        width: int = 1,
    ) -> None:
        """Highlight a cell centered on a point."""
        cell_colour = ImageColor.getcolor(colour.value, "RGB")

        buffer = Image.new("RGBA", self._image.size, (0, 0, 0, 0))
        buffer_draw = ImageDraw.Draw(buffer)

        for point in points:
            image_point = _world_to_screen(Point2D(point.x, point.z))
            buffer_draw.rectangle(
                (
                    image_point.x - 0.5 * size[0] * _PIXELS_PER_LIGHTYEAR,
                    image_point.y - 0.5 * size[1] * _PIXELS_PER_LIGHTYEAR,
                    image_point.x + 0.5 * size[0] * _PIXELS_PER_LIGHTYEAR,
                    image_point.y + 0.5 * size[1] * _PIXELS_PER_LIGHTYEAR,
                ),
                outline=cell_colour,
                width=width,
            )

        self._image.paste(
            buffer,
            buffer,
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
