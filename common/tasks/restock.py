"""Stores information about a carrier restock task."""

from dataclasses import dataclass

from common import Progress, System


@dataclass
class Tritium:
    """
    Stores information on the tritium a restock needs.

    required: Total tritium that needs to be delivered.
    initial: Value of "required" at task creation.
    delivered: Tritium that has been delivered to the depot.
    sell_price: Price tritum is sold at task completion.
    """

    required: int
    initial: int
    delivered: int
    sell_price: int | None

    @staticmethod
    def from_dict(data: dict) -> "Tritium":
        """Create an instance from a dictionary."""
        return Tritium(
            data["required"],
            data["initial"],
            data["delivered"],
            data["sell_price"],
        )


@dataclass
class Restock:
    """Stores information on a carrier restock task."""

    carrier: tuple[str, str]
    tritium: Tritium
    system: System
    haulers: list[int]
    progress: Progress
    message: int

    def __init__(
        self,
        carrier: tuple[str, str],
        tritium: dict,
        system: System,
        haulers: list[int],
        progress: dict,
        message: int,
    ) -> None:
        self.carrier = carrier
        self.tritium = Tritium.from_dict(tritium)
        self.system = system
        self.haulers = haulers
        self.progress = Progress.from_dict(progress)
        self.message = message

    def __str__(self) -> str:
        return f"[{self.carrier[0]}] {self.carrier[1]}"

    def __hash__(self) -> int:
        return hash(self.message)
