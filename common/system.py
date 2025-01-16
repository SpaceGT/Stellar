"""Stores a system name and position."""

from dataclasses import dataclass
from typing import Any

from utils.points import Point3D


@dataclass(frozen=True)
class System:
    """Stores a system name and position."""

    name: str
    location: Point3D | None

    def __str__(self) -> str:
        return self.name

    def __eq__(self, value: Any):
        if isinstance(value, System):
            return self.name.lower() == value.name.lower()

        if isinstance(value, str):
            return self.name.lower() == value.lower()

        return False
