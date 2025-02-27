"""Run asyncio coroutines at specific times."""

import asyncio
import datetime as dt
import logging
from datetime import datetime
from typing import Awaitable, Callable

_LOGGER = logging.getLogger(__name__)


async def sleep_until(date: datetime) -> None:
    """Sleep until the specified time."""
    now = datetime.now()
    await asyncio.sleep((date - now).total_seconds())


async def run_daily(
    time: dt.time,
    function: Callable[[], Awaitable[None]],
) -> asyncio.Task:
    """Run a function at a given time each day."""
    name = f"{function.__name__}-{time.strftime('%H:%M')}"

    async def task():
        while True:
            now = datetime.now()
            target = datetime.combine(now.date(), time)

            if now > target:
                target += dt.timedelta(days=1)

            await sleep_until(target)

            try:
                await function()
            except Exception:
                _LOGGER.exception("Error when performing %s", name)

    return asyncio.create_task(task(), name=name)
