"""Run asyncio coroutines at specific times."""

import asyncio
import datetime as dt
from datetime import datetime
from typing import Awaitable, Callable


async def sleep_until(date: datetime) -> None:
    """Sleep until the specified time."""
    now = datetime.now()
    await asyncio.sleep((date - now).total_seconds())


async def run_daily(
    time: dt.time,
    function: Callable[[], Awaitable[None]],
) -> asyncio.Task:
    """Run a function at a given time each day."""

    async def task():
        while True:
            now = datetime.now()
            target = datetime.combine(now.date(), time)

            if now > target:
                target += dt.timedelta(days=1)

            await sleep_until(target)
            await function()

    return asyncio.create_task(
        task(),
        name=f"{time.strftime('%H:%M')} Daily ({function.__name__})",
    )
