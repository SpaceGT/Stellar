"""Holds information on a depot."""

from dataclasses import dataclass
from datetime import datetime, timezone

from common import Good, System
from common.enums import Colour
from settings import TIMINGS


@dataclass
class Depot:
    """Holds information on a depot."""

    name: str
    system: System
    market: list[Good]
    market_id: int
    inara_url: str
    last_update: datetime

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.name)

    @property
    def tritium(self) -> Good | None:
        """Return the tritium in the market."""
        return next(iter(good for good in self.market if good.name == "tritium"), None)

    @property
    def colour(self) -> Colour:
        """Give the depot a colour representing the overall state."""

        if datetime.now(timezone.utc) - self.last_update > TIMINGS.market_expiry:
            return Colour.PURPLE

        if not self.tritium:
            return Colour.PURPLE

        if self.tritium.stock.quantity >= 15000:
            return Colour.GREEN

        if self.tritium.stock.quantity >= 7500:
            return Colour.YELLOW

        return Colour.RED
