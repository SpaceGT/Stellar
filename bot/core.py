"""Handles direct communication with Discord."""

import asyncio
import importlib
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

import discord
from discord import Client, Intents, Interaction, VoiceClient, app_commands
from discord.ext.commands import Cog, GroupCog
from discord.utils import MISSING

from settings import DISCORD

VoiceClient.warn_nacl = False
logging.getLogger("discord").setLevel(logging.WARN)

_LOGGER = logging.getLogger(__name__)
_CURRENT_DIR = Path(__file__).parent


def _get_module_func(path: Path, name: str = "main") -> Callable | None:
    relative_path = path.relative_to(_CURRENT_DIR)
    module_path = "." + ".".join(relative_path.parts)[:-3]
    module = importlib.import_module(module_path, "bot")

    if hasattr(module, name):
        return getattr(module, name)

    return None


def load_file(path: Path, entry: str = "main") -> None:
    """Run an entry function in a file."""
    main = _get_module_func(path, entry)
    assert main
    main()


async def load_async_file(path: Path, entry: str = "main") -> None:
    """Await an entry function in a file."""
    main = _get_module_func(path, entry)
    assert main
    await main()


class Core(Cog):
    """Commands needed for basic bot maintenance."""

    @app_commands.command(  # type: ignore [arg-type]
        name="shutdown",
        description="Sends a signal for a clean exit.",
    )
    async def shutdown(self, interaction: Interaction[Client]) -> None:
        """Sends a signal for a clean exit."""
        response = "## :zap: Shutting Down :zap:"
        await interaction.response.send_message(response, ephemeral=True)

        # Awaiting the response will give us a cancelled error
        asyncio.create_task(interaction.client.close(), name="Suicide")


class Bot(Client):
    """Wrapper for interacting with Discord"""

    def __init__(self) -> None:
        super().__init__(intents=Intents.default())
        self._tree = app_commands.CommandTree(self)

        self._should_sync = False
        self._ensure_messages = False

        self._main_guild = discord.Object(id=DISCORD.main_guild_id)
        self._test_guild = discord.Object(id=DISCORD.test_guild_id)

        self.setup_complete = asyncio.Event()

    async def setup_hook(self) -> None:
        self.load_cog(Core(), DISCORD.test_guild_id)
        self.setup_complete.clear()

        cog_files: list[Path] = []
        cog_files.extend((_CURRENT_DIR / "admin").glob("*.py"))
        cog_files.extend((_CURRENT_DIR / "misc").glob("*.py"))

        cog_files.append(_CURRENT_DIR / "rescue" / "prompt.py")
        cog_files.append(_CURRENT_DIR / "rescue" / "slash.py")
        cog_files.append(_CURRENT_DIR / "rescue" / "view.py")

        cog_files.append(_CURRENT_DIR / "restock" / "slash.py")
        cog_files.append(_CURRENT_DIR / "restock" / "view.py")

        # Remote all paths pointing to an __init__.py
        cog_files = list(filter(lambda x: x.stem != "__init__", cog_files))

        for cog_file in cog_files:
            load_file(cog_file)

    async def on_ready(self) -> None:
        """Acknowledge the logon."""
        assert self.application
        _LOGGER.info("Logged in as %s", self.application.name)

        if self._should_sync:
            self._should_sync = False

            global_commands = await self._tree.sync()
            _LOGGER.info("Synced %s global slash commands.", len(global_commands))

            main_commands = await self._tree.sync(guild=self._main_guild)
            _LOGGER.info("Synced %s main guild slash commands.", len(main_commands))

            test_commands = await self._tree.sync(guild=self._test_guild)
            _LOGGER.info("Synced %s test guild slash commands.", len(test_commands))

        if self._ensure_messages:
            self._ensure_messages = False

            targets: list[Path] = []
            targets.append(_CURRENT_DIR / "rescue" / "prompt.py")
            for target in targets:
                await load_async_file(target, "ensure_message")

        self.setup_complete.set()

    def reset_commands(self) -> None:
        """Delete and re-sync all slash commands."""
        self._tree.clear_commands(guild=None)
        self._tree.clear_commands(guild=self._main_guild)
        self._tree.clear_commands(guild=self._test_guild)
        self._should_sync = True

    def ensure_messages(self) -> None:
        """Verify and re-create all persistent messages."""
        self._ensure_messages = True

    def load_cog(
        self,
        cog: Cog,
        guild_id: int | None = None,
    ) -> Cog:
        """Load a cog into a discord Client."""

        guild = discord.Object(id=guild_id) if guild_id else MISSING

        def callback_factory() -> Callable[[], Awaitable[None]]:
            async def callback(*args: Any, **kwargs: Any) -> None:
                await asyncio.gather(
                    *(
                        handler(*args, **kwargs)
                        for handler in getattr(callback, "callbacks")
                    )
                )

            return callback

        if isinstance(cog, GroupCog):
            # GroupCogs should always have a command
            assert cog.app_command is not None
            self._tree.add_command(cog.app_command, guild=guild)

        else:
            for app_command in cog.get_app_commands():
                self._tree.add_command(app_command, guild=guild)

        for hook, coroutine in cog.get_listeners():
            func: Callable | None = getattr(self, hook, None)

            if not func or not getattr(func, "callbacks", None):
                callback = callback_factory()
                new_callbacks = [coroutine]

                if func:
                    new_callbacks.append(func)

                setattr(callback, "callbacks", new_callbacks)
                setattr(self, hook, callback)

                continue

            callbacks: list[Callable] = getattr(func, "callbacks")
            callbacks += [coroutine]

        return cog


CLIENT = Bot()
