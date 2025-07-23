"""Ping a webhook when an error is encountered."""

import asyncio
import logging
from io import BytesIO

from aiohttp import ClientSession
from discord import File
from discord import SyncWebhook as SyncDiscordWebhook
from discord import Webhook as AsyncDiscordWebhook
from discord import utils

from .models.webhooks import Webhooks


def _sync_send(url: str, message: str, file: str | None = None) -> None:
    bytes_io = None
    discord_file = utils.MISSING

    if file is not None:
        bytes_io = BytesIO(file.encode("utf-8"))
        discord_file = File(bytes_io, "log.txt")

    webhook = SyncDiscordWebhook.from_url(url)
    webhook.send(message, file=discord_file)

    if isinstance(discord_file, File) and isinstance(bytes_io, BytesIO):
        discord_file.close()
        bytes_io.close()


async def _async_send(url: str, message: str, file: str | None = None) -> None:
    bytes_io = None
    discord_file = utils.MISSING

    if file is not None:
        bytes_io = BytesIO(file.encode("utf-8"))
        discord_file = File(bytes_io, "log.txt")

    async with ClientSession() as session:
        webhook = AsyncDiscordWebhook.from_url(url, session=session)
        await webhook.send(message, file=discord_file)

    if isinstance(discord_file, File) and isinstance(bytes_io, BytesIO):
        discord_file.close()
        bytes_io.close()


def add_handler(main: str | None, fallback: str | None, level: int) -> None:
    root_logger = logging.getLogger()

    if main:
        root_logger.addHandler(Webhook(main, level))

    elif fallback and main != "":
        root_logger.addHandler(Webhook(fallback, level))


def setup(webhooks: Webhooks) -> None:
    add_handler(webhooks.critical, webhooks.fallback, logging.CRITICAL)
    add_handler(webhooks.error, webhooks.fallback, logging.ERROR)
    add_handler(webhooks.warning, webhooks.fallback, logging.WARNING)
    add_handler(webhooks.info, webhooks.fallback, logging.INFO)
    add_handler(webhooks.debug, webhooks.fallback, logging.DEBUG)


class Webhook(logging.Handler):
    """Ping a webhook when an error is encountered."""

    def __init__(self, webhook: str, level: int) -> None:
        super().__init__()
        self.webhook = webhook
        self.level = level

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno != self.level:
            return

        message = (
            f"```\n[{record.asctime}] [{record.levelname}] "
            + f"[{record.name}] {record.getMessage()}\n```"
        )

        file = None
        if record.exc_text:
            if len(message + record.exc_text) > 1900:
                file = record.exc_text
            else:
                message += f"\n```\n{record.exc_text}\n```"

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            _sync_send(self.webhook, message, file)
        else:
            task = loop.create_task(
                _async_send(self.webhook, message, file), name="Webhook"
            )
            task.add_done_callback(lambda task: task.exception())
