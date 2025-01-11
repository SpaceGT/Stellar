"""Entry point for Stellar"""

import asyncio
import logging
import platform
import signal
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime, timedelta, timezone
from types import FrameType
from typing import Unpack

import settings
from bot import rescue, restock
from bot.core import CLIENT
from external.eddn import listener as EddnListener
from services.depots import DEPOT_SERVICE
from services.rescues import RESCUE_SERVICE
from services.restocks import RESTOCK_SERVICE
from storage.sheet import SPREADSHEET
from utils import tick as asynctick

_LOGGER = logging.getLogger(__name__)


def _load_args() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument(
        "--update", action="store_true", help="Refresh all data from EDSM."
    )
    parser.add_argument(
        "--sync-tree", action="store_true", help="Sync all slash commands."
    )
    parser.add_argument(
        "--ensure-message", action="store_true", help="Verify all persistent messages."
    )
    parser.add_argument(
        "--tick", action="store_true", help="Tick on startup regardless of time."
    )
    parser.add_argument(
        "--ephemeral", action="store_true", help="Exit instead of monitoring EDDN."
    )
    return parser.parse_args()


def _shutdown(*_: Unpack[tuple[int, FrameType | None]]) -> None:
    _LOGGER.debug("Recieved SIGINT")

    if getattr(_shutdown, "handled", False):
        _LOGGER.error("Skipping clean shutdown")
        sys.exit(1)

    async def close_discord() -> None:
        _LOGGER.info("Queued Discord shutdown")
        await CLIENT.setup_complete.wait()
        await CLIENT.close()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _LOGGER.error("Could not find asyncio loop")
    else:
        loop.create_task(close_discord())

    setattr(_shutdown, "handled", True)


async def tick() -> None:
    """Called once per day."""
    update_expiry = timedelta(days=90)

    await DEPOT_SERVICE.inara_update()
    await rescue.write_revive()
    await restock.write_revive()

    for carrier in DEPOT_SERVICE.carriers:
        if not carrier.active_depot:
            continue

        if datetime.now(timezone.utc) - carrier.last_update > update_expiry:
            await restock.write_market_alert(carrier)


async def main() -> None:
    """Entry point for Stellar"""

    args = _load_args()

    _LOGGER.info("Started pulling from sheet")
    await SPREADSHEET.async_pull()

    await RESCUE_SERVICE.pull(lazy=True)
    await RESTOCK_SERVICE.pull(lazy=True)
    await DEPOT_SERVICE.pull(lazy=True)

    if args.sync_tree:
        CLIENT.reset_commands()

    if args.ensure_message:
        CLIENT.ensure_messages()

    discord_future = asyncio.gather(CLIENT.start(settings.DISCORD.token))
    await CLIENT.setup_complete.wait()

    if args.update:
        await DEPOT_SERVICE.update_all()

    tick_task = await asynctick.run_daily(settings.SOFTWARE.tick, tick)
    if args.tick:
        await tick()

    EddnListener.commodity += DEPOT_SERVICE.listener
    EddnListener.start()

    if args.ephemeral:
        await CLIENT.close()

    # Wait for bot to close
    await discord_future
    _LOGGER.info("Discord bot shut down.")

    tick_task.cancel()
    EddnListener.close()

    # Allow the remaining tasks to finish closing
    task = asyncio.current_task()
    assert task
    tasks = asyncio.all_tasks()
    tasks.remove(task)
    await asyncio.wait(tasks)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _shutdown)

    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
    sys.exit(0)
