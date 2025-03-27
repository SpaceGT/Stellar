"""Shared Companion API utility functions."""

from datetime import datetime, timezone

from common import Good
from external.eddn import upload

from ..depots import DEPOT_SERVICE
from .worker import CAPI_WORKER


async def sync_carrier(
    name: tuple[str, str], market_id: int, market: list[Good], system: str
) -> None:
    """Sync a known carrier internally and externally."""
    timestamp = datetime.now(timezone.utc)

    CAPI_WORKER.cache_update(name[0], timestamp)

    await DEPOT_SERVICE.listener(
        station=name[0],
        system=system,
        market=market,
        market_id=market_id,
        timestamp=timestamp,
    )

    await upload.commodity(
        station=name[0],
        system=system,
        market=market,
        market_id=market_id,
        uploader="CAPI-Fleetcarrier",
        timestamp=timestamp,
    )
