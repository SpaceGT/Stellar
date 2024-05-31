"""Stores a system name and position."""

from dataclasses import dataclass

from utils.points import Point3D


@dataclass(frozen=True)
class System:
    """Stores a system name and position."""

    name: str
    location: Point3D

    def __str__(self) -> str:
        return self.name
