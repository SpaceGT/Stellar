"""Handles task timing configuration."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any


@dataclass(frozen=True)
class Timings:
    """Information to use for scheduling tasks."""

    market_expiry: timedelta
    market_warning: timedelta
    task_revive: timedelta
    market_followup: timedelta
    capi_followup: timedelta
    tick: time


def factory(json: dict[str, Any]) -> Timings:
    """Create a Timings config object."""

    market_expiry = timedelta(days=json["market_expiry"])
    market_warning = timedelta(days=json["market_warning"])
    task_revive = timedelta(days=json["task_revive"])

    market_followup = timedelta(hours=json["market_followup"])
    capi_followup = timedelta(hours=json["capi_followup"])

    tick = datetime.strptime(json["tick"], "%H:%M").time()

    return Timings(
        market_expiry,
        market_warning,
        task_revive,
        market_followup,
        capi_followup,
        tick,
    )
