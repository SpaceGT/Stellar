"""Enum for storing task progress."""

from enum import StrEnum


class Stage(StrEnum):
    """Enum for storing task progress."""

    PENDING = "Pending"
    UNDERWAY = "Underway"
    COMPLETE = "Complete"
    ABORTED = "Aborted"
