"""Enum for storing CAPI sync states."""

from enum import StrEnum


class State(StrEnum):
    """Enum for storing CAPI sync states."""

    UNLISTED = "Unlisted"
    EXPIRED = "Expired"
    SYNCING = "Syncing"
