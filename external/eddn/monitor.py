"""Listens for data from EDDN."""

import asyncio
import json
import logging
import zlib
from asyncio import Task
from datetime import datetime, timedelta, timezone
from typing import Any

import zmq
from zmq import error as zmq_error
from zmq.asyncio import Context

from common import Good
from utils.events import AsyncEvent

_LOGGER = logging.getLogger(__name__)


class Monitor:
    """Listens for data from EDDN."""

    _ENDPOINT = "tcp://eddn.edcd.io:9500"
    _TIMEOUT = 15000

    def __init__(self) -> None:
        self._context = Context()

        self._socket = self._context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.setsockopt(zmq.SUBSCRIBE, b"")
        self._socket.setsockopt(zmq.RCVTIMEO, Monitor._TIMEOUT)
        self._socket.setsockopt(zmq.MAXMSGSIZE, 2**32)

        self._task: Task | None = None
        self._restarts: tuple[int, datetime | None] = (0, None)

        self.commodity = AsyncEvent()

    def start(self) -> None:
        """Starts monitoring EDDN."""
        assert self._task is None, "Listener started twice."

        self._socket.connect(Monitor._ENDPOINT)
        self._task = asyncio.create_task(self._monitor(), name="monitor")

        _LOGGER.info("EDDN listener started")

    def close(self) -> None:
        """Stops monitoring EDDN."""
        assert self._task, "Listener is already closed."

        self._task.cancel()
        self._socket.disconnect(Monitor._ENDPOINT)

        self._task = None

    async def _restart(self) -> None:
        """Restarts in-progress monitoring."""
        initial_delay = 5
        exp_factor = 4
        max_delay = 3 * 60**2
        ignore = 1 * 60**2

        wait_delay: int | None = None

        if self._restarts[1]:
            delta = datetime.now(timezone.utc) - self._restarts[1]

            if delta.total_seconds() > ignore:
                self._restarts = (0, None)
                wait_delay = min(initial_delay, max_delay)

        if wait_delay is None:
            wait_delay = min(
                initial_delay * exp_factor ** self._restarts[0],
                max_delay,
            )
            self._restarts = (
                self._restarts[0] + 1,
                datetime.now(timezone.utc) + timedelta(seconds=wait_delay),
            )

        self.close()
        await asyncio.sleep(wait_delay)
        self.start()

    async def _monitor(self) -> None:
        while True:
            try:
                response = await self._socket.recv_multipart()

            except zmq_error.Again:
                _LOGGER.warning("Reconnecting due to ZMQ Again.")
                asyncio.create_task(self._restart(), name="Monitor Restart")

            except zmq_error.ZMQError:
                _LOGGER.exception("ZMQError Raised")

            else:
                assert len(response) == 1

                message = zlib.decompress(response[0])
                decoded = message.decode()
                data = json.loads(decoded)

                self._process(data)

    def _process(self, data: dict[str, Any]) -> None:
        if "https://eddn.edcd.io/schemas/commodity/3" in data["$schemaRef"]:
            asyncio.create_task(
                self._commodity(data),
                name=f"Commodity ({data['message']['marketId']})",
            )

    async def _commodity(self, data: dict[str, Any]) -> None:
        await self.commodity.fire(
            data["message"]["stationName"],
            data["message"]["systemName"],
            [
                Good(
                    commodity["name"],
                    {
                        "price": commodity["buyPrice"],
                        "quantity": commodity["stock"],
                        "bracket": commodity["stockBracket"],
                    },
                    {
                        "price": commodity["sellPrice"],
                        "quantity": commodity["demand"],
                        "bracket": commodity["demandBracket"],
                    },
                    commodity["meanPrice"],
                )
                for commodity in data["message"]["commodities"]
            ],
            datetime.fromisoformat(
                data["message"]["timestamp"].removesuffix("Z"),
            ).replace(tzinfo=timezone.utc),
        )
