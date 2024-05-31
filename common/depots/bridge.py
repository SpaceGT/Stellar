"""Holds information on a Colonia Bridge station."""

from dataclasses import dataclass

from .depot import Depot


@dataclass
class Bridge(Depot):
    """Holds information on a Colonia Bridge station."""

    def __hash__(self) -> int:
        return hash(self.name)
