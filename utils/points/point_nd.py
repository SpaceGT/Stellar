"""Represents a point in space."""

from math import dist, hypot


class _PointND:
    """Represents a point in arbitrary dimensions."""

    def __init__(self, *args: float) -> None:
        self.ordinates = list(args)

    def __str__(self) -> str:
        return f"({', '.join(map(str, self.ordinates))})"

    def __add__(self, other: "_PointND") -> "_PointND":
        args: list[float] = []

        for o1, o2 in zip(self.ordinates, other.ordinates, strict=True):
            args.append(o1 + o2)

        return _PointND(*args)

    def __sub__(self, other: "_PointND") -> "_PointND":
        args: list[float] = []

        for o1, o2 in zip(self.ordinates, other.ordinates, strict=True):
            args.append(o1 - o2)

        return _PointND(*args)

    def distance(self, other: "_PointND") -> float:
        """Calculate the Euclidean distance to another ND point."""
        return dist(self.ordinates, other.ordinates)

    @property
    def magnitude(self) -> float:
        """Returns the distance from the origin."""
        return hypot(*self.ordinates)
