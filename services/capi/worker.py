"""Updates depots through the Companion API."""

import asyncio
import logging
from asyncio import Future, Task
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from aiohttp import ClientConnectionError

from common.depots import Carrier
from common.enums import State
from external.capi import CapiFail, EpicFail
from external.capi.auth import RefreshFail
from settings import CAPI
from utils.events import AsyncEvent

from ..depots import DEPOT_SERVICE
from .service import CAPI_SERVICE

_LOGGER = logging.getLogger(__name__)

_INTERVAL = timedelta(hours=2)
_DELAY = timedelta(minutes=1)


@dataclass
class SimpleCarrier:
    """Stores basic information on external carriers."""

    name: str
    last_update: datetime

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.name)


class CapiWorker:
    """Updates depots through the Companion API."""

    def __init__(self) -> None:
        self.sync: AsyncEvent = AsyncEvent()

        self._task: Task | None = None
        self._cache: dict[str, datetime] = {}

    def start(self) -> None:
        """Starts keeping depots updated with CAPI."""
        if self._task and not self._task.done():
            _LOGGER.warning("Ignoring duplicate start.")
            return

        for carrier in DEPOT_SERVICE.carriers:
            carrier.capi_status = CAPI_SERVICE.get_state(carrier.name)

        for callsign in CAPI_SERVICE.get_carriers():
            self._cache[callsign] = getattr(
                DEPOT_SERVICE.carriers.find(callsign),
                "last_update",
                datetime.now(timezone.utc),
            )

        self._task = asyncio.create_task(self._worker(), name="worker")
        self._task.add_done_callback(self._error)

        _LOGGER.info("CAPI worker started")

    def close(self) -> None:
        """Stops keeping depots updated with CAPI."""
        if not self._task or self._task.done():
            _LOGGER.warning("Ignoring duplicate close.")
            return

        self._task.cancel()
        self._task = None

    def cache_update(self, callsign: str, update: datetime) -> None:
        """Cache the update time of an external carrier."""
        self._cache[callsign] = update

    def _error(self, future: Future) -> None:
        if future.cancelled():
            return

        error = future.exception()
        _LOGGER.exception("CAPI worker aborted!", exc_info=error)

    def _get_external(self) -> list[SimpleCarrier]:
        """
        Returns all unregistered CAPI carriers with their last known update.
        Update time is fetched from cache or is otherwise the latest possible.
        """
        carriers: list[SimpleCarrier] = []
        for callsign in CAPI_SERVICE.get_carriers():
            if DEPOT_SERVICE.carriers.find(callsign):
                continue

            state = CAPI_SERVICE.get_state(callsign)
            if state == State.SYNCING or CAPI.use_epic and state == State.PARTIAL:
                update = self._cache.get(callsign, datetime.now(timezone.utc))
                carriers.append(SimpleCarrier(callsign, update))

        return carriers

    def _oldest_carrier(self, external: bool = True) -> Carrier | SimpleCarrier:
        """Get the carrier with the oldest market on CAPI."""
        carriers: list[Carrier | SimpleCarrier] = []

        for carrier in DEPOT_SERVICE.carriers:
            state = CAPI_SERVICE.get_state(carrier.name)
            if state == State.SYNCING or CAPI.use_epic and state == State.PARTIAL:
                carriers.append(carrier)

        if external:
            carriers.extend(self._get_external())

        carriers.sort(key=lambda x: x.last_update)

        if not carriers:
            raise ValueError

        return carriers[0]

    async def _next_target(
        self,
        interval: timedelta = _INTERVAL,
    ) -> Carrier | SimpleCarrier:
        while True:
            carrier = self._oldest_carrier()
            delay = (carrier.last_update + interval) - datetime.now(timezone.utc)
            await asyncio.sleep(max(delay.total_seconds(), 0))

            if self._oldest_carrier() == carrier:
                break

        return carrier

    async def _worker(self) -> None:
        while True:
            try:
                carrier = await self._next_target()
            except ValueError:
                _LOGGER.warning("Worker sleeping due to lack of jobs.")
                await asyncio.sleep(_INTERVAL.total_seconds())
                continue

            try:
                response = await CAPI_SERVICE.fleetcarrier(carrier.name)

            except ClientConnectionError:
                _LOGGER.warning("Worker retrying due to connection error.")
                await asyncio.sleep(_INTERVAL.total_seconds())
                continue

            except EpicFail:
                _LOGGER.warning("Skipping '%s' due to Epic error.", str(carrier))
                await asyncio.sleep(_DELAY.total_seconds())
                continue

            except CapiFail:
                _LOGGER.warning("Worker retrying due to internal cAPI error.")
                await asyncio.sleep(_INTERVAL.total_seconds())
                continue

            except RefreshFail:
                _LOGGER.warning("Skipping '%s' due to token expiry.", str(carrier))
                await asyncio.sleep(_DELAY.total_seconds())
                continue

            if not response:
                _LOGGER.warning("Disabling '%s' as it no longer exists.", str(carrier))

                if isinstance(carrier, Carrier):
                    carrier.active_depot = False
                else:
                    self._cache.pop(carrier.name, None)

                await CAPI_SERVICE.push()
                await DEPOT_SERVICE.push()

                await asyncio.sleep(_DELAY.total_seconds())
                continue

            if isinstance(carrier, Carrier):
                carrier.capi_status = CAPI_SERVICE.get_state(carrier.name)

            await self.sync.fire(
                name=(response[0][0], response[0][1]),
                market_id=response[0][2],
                market=response[1],
                system=response[2],
            )
            await asyncio.sleep(_DELAY.total_seconds())


CAPI_WORKER = CapiWorker()
