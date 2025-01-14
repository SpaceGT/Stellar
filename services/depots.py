"""Provide a way to access and update all depots."""

import asyncio
import logging
import re
from datetime import datetime
from typing import Iterable, Iterator

from thefuzz import process  # type: ignore [import-untyped]

from common import Good, System
from common.depots import Bridge, Carrier, Depot
from external import edsm, inara
from storage import bridges, carriers

from .restocks import RESTOCK_SERVICE

_LOGGER = logging.getLogger(__name__)


def _log_tritium(depot: Depot) -> None:
    if depot.tritium:
        if isinstance(depot, Carrier):
            if depot.tritium.demand.quantity > 0:
                order_type = "buying"
                market = depot.tritium.demand
            else:
                order_type = "selling"
                market = depot.tritium.stock
        else:
            order_type = "selling"
            market = depot.tritium.stock

        _LOGGER.info(
            "'%s' in '%s' is %s %s tonnes of tritium at %s cr/t (%s other orders)",
            str(depot),
            depot.system.name,
            order_type,
            market.quantity,
            market.price,
            len(depot.market) - 1,
        )

    else:
        _LOGGER.info(
            "'%s' in '%s' does not trade tritium (%s other orders)",
            str(depot),
            depot.system.name,
            len(depot.market),
        )


async def update_depot(
    depot: Depot,
    system: System,
    market: list[Good],
    timestamp: datetime,
    push: bool = True,
) -> None:
    """Modify depot market data."""

    depot.market = market
    depot.system = system
    depot.last_update = timestamp

    _log_tritium(depot)

    if isinstance(depot, Carrier):
        await RESTOCK_SERVICE.try_restock(depot, push)


class _Carriers:
    def __init__(self, depots: Iterable[Carrier]) -> None:
        self._carriers: set[Carrier] = set(depots)

    def __len__(self) -> int:
        return len(self._carriers)

    def __iter__(self) -> Iterator[Carrier]:
        return iter(self._carriers)

    def find(self, callsign: str = "", display_name: str = "") -> Carrier | None:
        """Find a single carrier with the given name and/or callsign."""

        for depot in self._carriers:
            if callsign and depot.name != callsign:
                continue

            if display_name and depot.display_name != display_name:
                continue

            return depot

        return None

    def search(self, display_name: str, inactive: bool = False) -> list[Carrier]:
        """Return a confidence-ordered list of carriers based on a display name."""
        depots = [
            depot for depot in self._carriers if depot.active_depot == (not inactive)
        ]

        if display_name == "":
            return depots

        output = [
            carrier
            for carrier, _ in process.extract(
                display_name,
                depots,
                processor=str,
                limit=len(depots),
            )
        ]

        return output


class _Bridges:
    def __init__(self, depots: Iterable[Bridge]) -> None:
        self._bridges: set[Bridge] = set(depots)

    def __len__(self) -> int:
        return len(self._bridges)

    def __iter__(self) -> Iterator[Bridge]:
        return iter(self._bridges)

    def find(self, name: str = "") -> Bridge | None:
        """Find a single bridge with the given name."""
        return next(
            iter(bridge for bridge in self._bridges if bridge.name == name), None
        )

    def search(self, display_name: str) -> list[Bridge]:
        """Return a confidence-ordered list of bridges based on a display name."""
        depots = list(self._bridges)

        if display_name == "":
            return depots

        output = [
            bridge
            for bridge, _ in process.extract(
                display_name,
                depots,
                processor=str,
                limit=len(depots),
            )
        ]

        return output


class DepotService:
    """Provide a way to access and update all depots."""

    def __init__(self) -> None:
        self.bridges = _Bridges([])
        self.carriers = _Carriers([])

        RESTOCK_SERVICE.status_change += lambda depot, status: setattr(
            self.carriers.find(callsign=depot), "restock_status", status
        )

    async def pull(self, lazy: bool = False) -> None:
        """Fetch the latest list of depots."""
        self.bridges = _Bridges(await bridges.load_bridges(lazy))
        self.carriers = _Carriers(await carriers.load_carriers(lazy))

        for carrier in self.carriers:
            carrier.restock_status = RESTOCK_SERVICE.restock_status(carrier)

        _LOGGER.debug("Pulled depots")

    async def push(self) -> None:
        """Push the latest list of depots."""
        await bridges.push_bridges(list(self.bridges))
        await carriers.push_carriers(list(self.carriers))

        _LOGGER.debug("Pushed depots")

    async def listener(
        self,
        station: str,
        system: str,
        market: list[Good],
        timestamp: datetime,
    ) -> None:
        """Subscribe to an EDDN commodity feed for automatic depot updates."""

        depot = self.bridges.find(station) or self.carriers.find(station)

        if not depot or timestamp < depot.last_update:
            return

        if isinstance(depot, Carrier) and depot.system.name != system:
            system_data = await edsm.system(system)
            assert system_data
        else:
            system_data = depot.system

        await update_depot(depot, system_data, market, timestamp)
        await self.push()

    @property
    def depots(self) -> list[Depot]:
        """Return all depots regardless of type."""
        depots: list[Depot] = []

        depots += sorted(self.carriers, key=lambda x: x.display_name)  # type: ignore [attr-defined]
        depots += sorted(self.bridges, key=lambda x: x.name)

        return depots

    async def verify(self) -> None:
        """
        Check all depots for unprocessed changes.
        Colours are calculated when the depot is pushed.
        Depots with missing fields will not be loaded in the first place.
        """

        for carrier in self.carriers:
            await RESTOCK_SERVICE.try_restock(carrier, push=False)

        await RESTOCK_SERVICE.push()
        await self.push()

    async def edsm_update(self) -> None:
        """Update all depots from EDSM."""

        _LOGGER.info("Starting EDSM update")

        for depot in self.depots:
            market, system, last_update = await edsm.overview(depot.market_id, True)

            if last_update is None:
                _LOGGER.info("'%s' does not have market data.", str(depot))
                continue

            if last_update <= depot.last_update:
                _LOGGER.info("'%s' is already up to date.", str(depot))
                continue

            await update_depot(depot, system, market, last_update, push=False)

        _LOGGER.info("Finished EDSM update")

        await RESTOCK_SERVICE.push()
        await self.push()

    async def inara_update(self, delay: int = 2500) -> None:
        """Update eligible carriers from INARA."""

        _LOGGER.info("Starting INARA update")

        for carrier in self.carriers:
            if carrier.inara_poll is False:
                continue

            search = re.search(
                r"^https:\/\/inara\.cz\/station\/(\d+)$", carrier.inara_url
            )
            assert search
            inara_id = int(search.group(1))

            try:
                market, system_name, last_update = await inara.overview(inara_id)
            except ValueError:
                _LOGGER.error("'%s' caused an error when updating.", str(carrier))
                continue

            if isinstance(carrier, Carrier) and carrier.system.name != system_name:
                system = await edsm.system(system_name)
                assert system
            else:
                system = carrier.system

            if market == []:
                _LOGGER.warning("'%s' does not have market data.", str(carrier))
                continue

            if last_update <= carrier.last_update:
                _LOGGER.info("'%s' is already up to date.", str(carrier))
                continue

            await update_depot(carrier, system, market, last_update, push=False)
            await asyncio.sleep(delay / 1000)

        _LOGGER.info("Finished INARA update")

        await RESTOCK_SERVICE.push()
        await self.push()


DEPOT_SERVICE = DepotService()
