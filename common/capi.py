"""Stores CAPI information for an account."""

from dataclasses import dataclass
from datetime import datetime

from common.enums import Service


@dataclass
class CapiData:
    """Stores CAPI information for an account."""

    customer_id: int
    auth_type: Service
    commander: str
    carrier: str | None
    discord_id: int
    access_token: tuple[str, datetime] | None
    refresh_token: str

    def __hash__(self):
        return hash(self.customer_id)
