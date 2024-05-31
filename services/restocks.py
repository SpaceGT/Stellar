"""Provide a way to access and update all restock tasks."""

import logging
from datetime import datetime, timezone
from typing import Iterable, Iterator, Literal

from thefuzz import process  # type: ignore [import-untyped]

from bot import restock as discord_restock
from common.depots import Carrier
from common.enums import Stage
from common.tasks import Restock
from services import galaxy
from storage import restocks
from utils.events import SyncEvent

_LOGGER = logging.getLogger(__name__)


class _Restocks:
    def __init__(self, tasks: Iterable[Restock]) -> None:
        self._restocks: set[Restock] = set(tasks)

    def __len__(self) -> int:
        return len(self._restocks)

    def __iter__(self) -> Iterator[Restock]:
        return iter(self._restocks)

    def find(
        self,
        callsign: str = "",
        display_name: str = "",
        message: int | None = None,
        stage: Stage | None = None,
        inlcude_complete: bool = False,
        include_aborted: bool = False,
    ) -> Restock | None:
        """Find a single restock task with the given criteria."""

        for task in self._restocks:
            if callsign and task.carrier[0] != callsign:
                continue

            if display_name and task.carrier[1] != display_name:
                continue

            if stage and task.progress.stage != stage:
                continue

            if not inlcude_complete and task.progress.stage == Stage.COMPLETE:
                continue

            if not include_aborted and task.progress.stage == Stage.ABORTED:
                continue

            if message and task.message != message:
                continue

            return task

        return None

    def search(self, display_name: str, complete: bool = False) -> list[Restock]:
        """Return a confidence-ordered list of restock tasks based on a display name."""
        tasks = [
            task
            for task in self._restocks
            if (complete or task.progress.stage != Stage.COMPLETE)
            and task.progress.stage != Stage.ABORTED
        ]

        if display_name == "":
            return tasks

        output = [
            task
            for task, _ in process.extract(
                display_name,
                tasks,
                processor=str,
                limit=len(tasks),
            )
        ]

        return output

    def add(self, restock: Restock) -> None:
        """Add a new restock to the collection."""
        self._restocks.add(restock)


class RestockService:
    """Provide a way to access and update all restock tasks."""

    def __init__(self) -> None:
        self.restocks = _Restocks([])
        self.status_change = SyncEvent()

        discord_restock.HAULER_UPDATE += self._on_hauler_update
        discord_restock.REGISTER_CAN_USE(self._can_assign_task)

    async def pull(self, lazy: bool = False) -> None:
        """Fetch the latest list of restock tasks."""
        self.restocks = _Restocks(await restocks.load_restocks(lazy))
        _LOGGER.debug("Pulled restock tasks")

    async def push(self) -> None:
        """Push the latest list of restock tasks."""
        await restocks.push_restocks(self.restocks)
        _LOGGER.debug("Pushed restock tasks")

    def restock_status(
        self, carrier: Carrier
    ) -> Literal[Stage.PENDING, Stage.UNDERWAY] | None:
        """Get the restock status for a given carrier."""

        task = self.restocks.find(callsign=carrier.name)

        if task is None:
            return None

        assert task.progress.stage in [Stage.UNDERWAY, Stage.PENDING]
        return task.progress.stage  # type: ignore [return-value]

    async def try_restock(self, depot: Carrier, push: bool = True) -> None:
        """Create or update a restock task for a carrier if required."""

        if not depot.active_depot:
            return

        if not depot.tritium:
            return

        if depot.tritium.demand.quantity > 0:
            return

        if depot.restock_status is None:
            if depot.tritium.stock.quantity > depot.reserve_tritium:
                return

            await self._new_restock(depot)

        else:
            restock = self.restocks.find(callsign=depot.name)
            assert restock

            delivered = depot.tritium.stock.quantity - (
                depot.allocated_space - restock.tritium.required
            )
            target = restock.tritium.required

            if delivered < 0:
                target = restock.tritium.required + delivered * -1
                delivered = 0

            await self._update_restock(depot, delivered, target)

            if delivered >= target * 0.8:
                await self.close_restock(depot, push=False)

        if push:
            await self.push()

    async def _update_restock(
        self,
        carrier: Carrier,
        delivered: int,
        target: int,
    ) -> None:
        restock = self.restocks.find(callsign=carrier.name)

        assert restock
        assert carrier.tritium

        restock.tritium.delivered = delivered
        restock.tritium.required = target

        await discord_restock.update_task(
            restock.message,
            carrier.tritium.stock.quantity,
            delivered,
            target,
        )

        _LOGGER.info(
            "Updated restock task for %s with %s/%s tritium",
            carrier,
            restock.tritium.delivered,
            restock.tritium.required,
        )

    async def _new_restock(self, carrier: Carrier) -> None:
        assert carrier.tritium

        tritium = {
            "required": carrier.allocated_space - carrier.tritium.stock.quantity,
            "initial": carrier.allocated_space - carrier.tritium.stock.quantity,
            "delivered": 0,
            "sell_price": None,
        }

        carrier.restock_status = Stage.PENDING

        with galaxy.render([carrier.system.location]) as gal_map:
            message_id = await discord_restock.write_task(carrier, gal_map)

        self.restocks.add(
            Restock(
                carrier=(carrier.name, carrier.display_name),
                haulers=[],
                progress={
                    "stage": Stage.PENDING,
                    "start": datetime.now(timezone.utc),
                    "end": None,
                },
                tritium=tritium,
                system=carrier.system,
                message=message_id,
            )
        )

        _LOGGER.info(
            "Created restock task for %s requiring %s tritium.",
            carrier,
            tritium["required"],
        )

    async def close_restock(
        self,
        carrier: Carrier,
        push: bool = True,
        abort: bool = False,
    ) -> None:
        """Close the restock task for a carrier."""

        restock = self.restocks.find(callsign=carrier.name)
        carrier.restock_status = None

        assert carrier.tritium
        assert restock

        if abort:
            restock.progress.stage = Stage.ABORTED
        else:
            restock.progress.stage = Stage.COMPLETE

        restock.progress.end = datetime.now(timezone.utc)
        restock.tritium.sell_price = carrier.tritium.stock.price or None

        await discord_restock.close_task(restock.message)

        _LOGGER.info(
            "Closed restock task for %s with %s/%s tritium",
            carrier,
            restock.tritium.delivered,
            restock.tritium.required,
        )

        if push:
            await self.push()

    def _can_assign_task(
        self,
        message_id: int,
        user_id: int,
        accepted: bool,
    ) -> bool:
        task = self.restocks.find(message=message_id)

        if not task:
            raise ValueError()

        if accepted and user_id in task.haulers:
            return False

        if not accepted and user_id not in task.haulers:
            return False

        return True

    async def update_hauler(self, task: Restock, user_id: int, accepted: bool) -> bool:
        """Update the hauler for a task."""

        if not self._can_assign_task(task.message, user_id, accepted):
            return False

        return await self._on_hauler_update(task.message, user_id, accepted)

    async def _on_hauler_update(
        self,
        message_id: int,
        user_id: int,
        accepted: bool,
    ) -> bool:
        """Callback to allow the task to update restocks."""
        task = self.restocks.find(message=message_id)

        if not task:
            raise ValueError()

        if accepted:
            task.haulers.append(user_id)

        else:
            task.haulers.remove(user_id)

        if task.haulers:
            task.progress.stage = Stage.UNDERWAY
        else:
            task.progress.stage = Stage.PENDING

        await discord_restock.update_stage(message_id, task.progress.stage)
        self.status_change.fire(task.carrier[0], task.progress.stage)

        await self.push()
        return True


RESTOCK_SERVICE = RestockService()
