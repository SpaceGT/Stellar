"""Provide a way to access and update all rescue tasks."""

import logging
from datetime import datetime, timezone
from typing import Iterable, Iterator

from thefuzz import process  # type: ignore [import-untyped]

from bot import rescue as discord_rescue
from common import System
from common.enums import Stage
from common.tasks import CarrierRescue, Rescue, ShipRescue
from services import galaxy
from storage import rescues

_LOGGER = logging.getLogger(__name__)


class _Rescues:
    def __init__(self, tasks: Iterable[Rescue]) -> None:
        self._rescues: set[Rescue] = set(tasks)

    def __len__(self) -> int:
        return len(self._rescues)

    def __iter__(self) -> Iterator[Rescue]:
        return iter(self._rescues)

    def find(
        self,
        client: int | None = 0,
        message: int | None = None,
        stage: Stage | None = None,
        inlcude_complete: bool = False,
        include_aborted: bool = False,
    ) -> Rescue | None:
        """Find a single restock task with the given criteria."""

        for task in self._rescues:
            if stage and task.progress.stage != stage:
                continue

            if not inlcude_complete and task.progress.stage == Stage.COMPLETE:
                continue

            if not include_aborted and task.progress.stage == Stage.ABORTED:
                continue

            if message and task.message != message:
                continue

            if client and task.client != client:
                continue

            return task

        return None

    def search(self, display_name: str, complete: bool = False) -> list[Rescue]:
        """Return a confidence-ordered list of rescue tasks based on a display name."""
        tasks = [
            task
            for task in self._rescues
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

    def add(self, rescue: Rescue) -> None:
        """Add a new restock to the collection."""
        self._rescues.add(rescue)


class RescueService:
    """Provide a way to access and update all rescue tasks."""

    def __init__(self) -> None:
        self.rescues = _Rescues([])

        discord_rescue.CLOSE_TASK += self.close_rescue
        discord_rescue.RESCUER_UPDATE += self._on_rescuer_update
        discord_rescue.REGISTER_CAN_USE(self._can_assign_task)

    async def pull(self, lazy: bool = False) -> None:
        """Fetch the latest list of tasks."""
        self.rescues = _Rescues(await rescues.load_rescues(lazy))
        _LOGGER.debug("Pulled rescue tasks")

    async def push(self) -> None:
        """Push the latest list of tasks."""
        await rescues.push_rescues(self.rescues)
        _LOGGER.debug("Pushed rescue tasks")

    def _can_assign_task(
        self,
        message_id: int,
        user_id: int,
        accepted: bool,
    ) -> bool:
        task = self.rescues.find(message=message_id)

        if not task:
            raise ValueError()

        if accepted and user_id in task.rescuers:
            return False

        if not accepted and user_id not in task.rescuers:
            return False

        return True

    async def update_rescuer(self, task: Rescue, user_id: int, accepted: bool) -> bool:
        """Update the rescuer for a task."""

        if not self._can_assign_task(task.message, user_id, accepted):
            return False

        return await self._on_rescuer_update(task.message, user_id, accepted)

    async def _on_rescuer_update(
        self,
        message_id: int,
        user_id: int,
        accepted: bool,
    ) -> bool:
        """Callback to allow the task to update rescues."""
        task = self.rescues.find(message=message_id)

        if not task:
            raise ValueError()

        if accepted:
            task.rescuers.append(user_id)

        else:
            task.rescuers.remove(user_id)

        if task.rescuers:
            task.progress.stage = Stage.UNDERWAY
        else:
            task.progress.stage = Stage.PENDING

        await discord_rescue.update_stage(message_id, task.progress.stage)

        await self.push()
        return True

    async def new_rescue(
        self,
        client: int,
        system: System,
        tritium: int | None = None,
    ) -> None:
        """Create a new rescue task."""
        if system.location is None:
            raise ValueError(f"Cannot find location for '{system}'")

        with galaxy.render([system.location]) as gal_map:
            message_id = await discord_rescue.write_task(
                client,
                system,
                tritium,
                gal_map,
            )

        rescue: Rescue
        if tritium is None:
            rescue = ShipRescue(
                client,
                system,
                rescuers=[],
                progress={
                    "stage": Stage.PENDING,
                    "start": datetime.now(timezone.utc),
                    "end": None,
                },
                message=message_id,
            )

        else:
            rescue = CarrierRescue(
                client,
                system,
                rescuers=[],
                progress={
                    "stage": Stage.PENDING,
                    "start": datetime.now(timezone.utc),
                    "end": None,
                },
                message=message_id,
                tritium=tritium,
            )

        self.rescues.add(rescue)

        await self.push()

    async def close_rescue(
        self,
        client: int,
        push: bool = True,
        abort: bool = False,
    ) -> None:
        """Close the active rescue task for a client."""

        rescue = self.rescues.find(client=client)
        assert rescue

        if abort:
            rescue.progress.stage = Stage.ABORTED
        else:
            rescue.progress.stage = Stage.COMPLETE

        rescue.progress.end = datetime.now(timezone.utc)

        await discord_rescue.close_task(rescue.message)

        # Logging is done inside calling function for easy access
        # to discord names

        if push:
            await self.push()


RESCUE_SERVICE = RescueService()
