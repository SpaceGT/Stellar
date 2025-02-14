"""Holds information on a fleet carrier depot."""

from dataclasses import dataclass
from typing import Literal

from common import System
from common.enums import Colour, Stage, State

from .depot import Depot


def stock_bracket(amount: int) -> Literal[0, 1, 2, 3]:
    """Calculate the stock bracket for a given tonnage."""
    capacity = 25000
    if amount >= capacity * 0.75:
        return 3

    if amount >= capacity * 0.25:
        return 2

    if amount > 0:
        return 1

    return 0


@dataclass
class Carrier(Depot):
    """Holds information on a fleet carrier depot."""

    display_name: str
    deploy_system: System
    reserve_tritium: int
    allocated_space: int
    owner_discord_id: int
    active_depot: bool

    capi_status: State | None = None
    restock_status: Literal[Stage.PENDING, Stage.UNDERWAY] | None = None

    def __str__(self) -> str:
        return f"[{self.name}] {self.display_name}"

    def __hash__(self) -> int:
        return hash((self.name, self.display_name))

    @property
    def colour(self) -> Colour:
        """Give the depot a colour representing the overall state."""
        if not self.active_depot:
            return Colour.BLACK

        if self.restock_status == Stage.UNDERWAY:
            return Colour.CYAN

        if self.restock_status == Stage.PENDING:
            return Colour.BLUE

        if self.system != self.deploy_system:
            return Colour.PURPLE

        if self.tritium and self.tritium.demand.quantity > 0:
            return Colour.PURPLE

        return super().colour
