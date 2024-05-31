"""Stores the state of a task."""

from dataclasses import dataclass
from datetime import datetime

from common.enums import Stage


@dataclass
class Progress:
    """Stores the state of a task."""

    stage: Stage
    start: datetime
    end: datetime | None

    @staticmethod
    def from_dict(data: dict) -> "Progress":
        """Create an instance from a dictionary."""
        return Progress(
            data["stage"],
            data["start"],
            data["end"],
        )
