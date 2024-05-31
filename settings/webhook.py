"""Ping a webhook when an error is encountered."""

import asyncio
import json
import logging

import aiohttp
import aiohttp.client_exceptions
import requests
from aiohttp import ClientSession

_TIMEOUT = 5
_HEADERS = {"Content-Type": "application/json"}


def _ping(url: str, data: dict[str, str]) -> bool:
    try:
        response = requests.post(
            url,
            headers=_HEADERS,
            data=json.dumps(data),
            timeout=_TIMEOUT,
        )

    except requests.exceptions.RequestException:
        return False

    if response.status_code != 200:
        return False

    return True


async def _async_ping(url: str, data: dict[str, str]) -> bool:
    try:
        async with ClientSession() as session:
            async with session.post(
                f"{url}",
                headers=_HEADERS,
                data=json.dumps(data),
                timeout=_TIMEOUT,
            ) as response:
                if response.status != 200:
                    return False

    except aiohttp.client_exceptions.ClientError:
        return False

    return True


class Webhook(logging.Handler):
    """Ping a webhook when an error is encountered."""

    def __init__(self, webhook: str):
        super().__init__()
        self.webhook = webhook
        self.setLevel(logging.WARNING)

    def emit(self, record: logging.LogRecord):
        message = (
            f"```\n[{record.asctime}] [{record.levelname}] "
            + f"[{record.name}] {record.getMessage()}\n```"
        )

        if record.exc_text:
            message += f"\n```\n{record.exc_text}\n```"

        if len(message) > 2000:
            message = message.removesuffix("\n```")[:1900]
            message += f"\n{len(message)} characters remaining...\n```"

        data = {"content": message}

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            _ping(self.webhook, data)
        else:
            loop.create_task(_async_ping(self.webhook, data), name="Webhook")
