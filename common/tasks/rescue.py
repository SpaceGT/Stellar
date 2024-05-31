"""Stores information about a rescue task."""

from common import Progress, System


class Rescue:
    """Stores information on a generic rescue task."""

    client: int
    system: System
    rescuers: list[int]
    progress: Progress
    message: int

    def __init__(
        self,
        client: int,
        system: System,
        rescuers: list[int],
        progress: dict,
        message: int,
    ) -> None:
        self.client = client
        self.system = system
        self.rescuers = rescuers
        self.progress = Progress.from_dict(progress)
        self.message = message

    def __str__(self) -> str:
        return f"{self.system.name} - <@{self.client}>"

    def __hash__(self) -> int:
        return hash(self.message)


class ShipRescue(Rescue):
    """Stores information on a ship rescue task."""

    def __hash__(self) -> int:
        return hash(self.message)


class CarrierRescue(Rescue):
    """Stores information on a carrier rescue task."""

    def __init__(
        self,
        client: int,
        system: System,
        rescuers: list[int],
        progress: dict,
        message: int,
        tritium: int,
    ) -> None:
        self.tritium = tritium
        super().__init__(client, system, rescuers, progress, message)

    def __hash__(self) -> int:
        return hash(self.message)
