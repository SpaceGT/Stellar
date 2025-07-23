"""Listens for data from EDDN."""

import asyncio
import json
import logging
import re
import zlib
from asyncio import Future, Task
from datetime import datetime, timedelta, timezone
from typing import Any

import zmq
from zmq import error as zmq_error
from zmq.asyncio import Context

from common import Good
from utils.events import AsyncEvent

_LOGGER = logging.getLogger(__name__)
_CARRIER = re.compile(r"^[A-Z0-9]{3}-[A-Z0-9]{3}$", re.MULTILINE)


class Monitor:
    """Listens for data from EDDN."""

    _ENDPOINT = "tcp://eddn.edcd.io:9500"
    _TIMEOUT = timedelta(seconds=15)
    _RETRY = timedelta(hours=2)

    def __init__(self) -> None:
        self._context = Context()

        self._socket = self._context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.setsockopt(zmq.SUBSCRIBE, b"")
        self._socket.setsockopt(zmq.MAXMSGSIZE, 2**32)

        timeout = int(Monitor._TIMEOUT.total_seconds() * 1000)
        self._socket.setsockopt(zmq.RCVTIMEO, timeout)

        self._task: Task | None = None
        self.commodity = AsyncEvent()

    def start(self) -> None:
        """Starts monitoring EDDN."""
        if self._task and not self._task.done():
            _LOGGER.warning("Worker is already running.")
            return

        self._socket.connect(Monitor._ENDPOINT)
        self._task = asyncio.create_task(self._monitor(), name="monitor")
        self._task.add_done_callback(self._error)

        _LOGGER.info("EDDN listener started")

    def close(self) -> None:
        """Stops monitoring EDDN."""
        if not self._task or self._task.done():
            return

        self._task.cancel()
        self._socket.disconnect(Monitor._ENDPOINT)

        self._task = None

    def _error(self, future: Future) -> None:
        if future.cancelled():
            return

        error = future.exception()
        _LOGGER.exception("EDDN listener aborted!", exc_info=error)

    async def _restart(self, delay: bool = False) -> None:
        """Restarts in-progress monitoring."""
        self.close()

        if delay:
            await asyncio.sleep(Monitor._RETRY.total_seconds())

        self.start()

    async def _monitor(self) -> None:
        while True:
            try:
                response = await self._socket.recv_multipart()

            except zmq_error.Again:
                _LOGGER.warning("Waiting for EDDN feed to resume.")
                asyncio.create_task(self._restart(True), name="Monitor Restart")

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
        is_carrier = _CARRIER.match(data["message"]["stationName"])

        market = [
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
        ]

        # Simple market validation
        message = [
            f"Ignoring bad commodity update for '{data['message']['stationName']}'"
        ]
        for good in market:

            # A bug makes some pesticides (ironic) buy and sell for free
            if good.name == "pesticides":
                continue

            issues = []

            buying = any((good.demand.quantity, good.demand.price))
            selling = any((good.stock.quantity, good.stock.price))

            if buying:
                if not good.demand.price:
                    issues.append("Buying for free.")

                if is_carrier:
                    if not good.demand.quantity:
                        issues.append("Buying without demand.")

            if selling:
                if not good.stock.price:
                    issues.append("Selling for free.")

            if buying and selling and is_carrier:
                issues.append("Buying and selling simultaneously.")

            if not (buying or selling):
                issues.append("Trading but not buying or selling.")

            if issues:
                message.extend([f"{good.name} - {len(issues)} issue(s)"] + issues)

        if len(message) > 1:
            _LOGGER.warning("\n".join(message))
            return

        await self.commodity.fire(
            data["message"]["stationName"],
            data["message"]["systemName"],
            market,
            data["message"]["marketId"],
            datetime.fromisoformat(
                data["message"]["timestamp"].removesuffix("Z"),
            ).replace(tzinfo=timezone.utc),
        )
