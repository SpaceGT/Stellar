"""Stores information about an in-game commodity."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class _Market:
    """Information about the market for that commodity."""

    price: int = 0
    quantity: int = 0
    bracket: Literal[0, 1, 2, 3, ""] = ""

    @staticmethod
    def from_dict(data: dict) -> "_Market":
        """Create an instance from a dictionary."""
        return _Market(
            data.get("price", 0),
            data.get("quantity", 0),
            data.get("bracket", ""),
        )


@dataclass(frozen=True)
class Good:
    """Stores information about an in-game commodity."""

    name: str
    stock: _Market
    demand: _Market
    mean_price: int

    def __init__(
        self,
        name: str,
        stock_info: dict,
        demand_info: dict,
        mean_price: int = 0,
    ) -> None:
        # Attrs should be set despite being frozen
        object.__setattr__(self, "name", name.lower())
        object.__setattr__(self, "stock", _Market.from_dict(stock_info))
        object.__setattr__(self, "demand", _Market.from_dict(demand_info))
        object.__setattr__(self, "mean_price", mean_price)

    def __str__(self) -> str:
        return self.name
