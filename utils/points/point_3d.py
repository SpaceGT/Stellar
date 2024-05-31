"""Represents a point in 3D space."""

from .point_nd import _PointND


class Point3D:
    """Represents a point in 3D space."""

    def __init__(self, x: float, y: float, z: float) -> None:
        self._point = _PointND(x, y, z)

    def __str__(self) -> str:
        return str(self._point)

    def __add__(self, other: "Point3D") -> "Point3D":
        return Point3D(*(self._point + other._point).ordinates)

    def __sub__(self, other: "Point3D") -> "Point3D":
        return Point3D(*(self._point - other._point).ordinates)

    @property
    def x(self) -> float:
        """Returns the x-value of the point."""
        return self._point.ordinates[0]

    @property
    def y(self) -> float:
        """Returns the y-value of the point."""
        return self._point.ordinates[1]

    @property
    def z(self) -> float:
        """Returns the z-value of the point."""
        return self._point.ordinates[2]

    @property
    def magnitude(self) -> float:
        """Returns the distance from the origin."""
        return self._point.magnitude

    def distance(self, other: "Point3D") -> float:
        """Calculate the Euclidean distance to another 3D point."""
        return self._point.distance(getattr(other, "_point"))
