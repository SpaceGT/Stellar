"""Quickly send memes through a slash command."""

import logging
from pathlib import Path

from discord import Client, File, Interaction, app_commands
from discord.app_commands import Choice
from discord.ext import commands
from thefuzz import process  # type: ignore [import-untyped]

from bot.core import CLIENT
from settings import DISCORD

_LOGGER = logging.getLogger(__name__)


class Meme(commands.Cog):
    """Quickly send memes through a slash command."""

    _MISSING: str = (
        "## :card_box: Missing Meme :card_box:\n"
        + "Consider using the autocomplete suggestions."
    )

    def __init__(self) -> None:
        self._memes: list[Path] = [
            meme
            for meme in DISCORD.meme_images.iterdir()
            if meme.suffix in [".png", ".mp4"]
        ]
        self._names: list[str] = [
            path.stem.lower().replace(" ", "-") for path in self._memes
        ]

    @app_commands.command(  # type: ignore [arg-type]
        name="meme",
        description="Send a meme of your choosing to the current channel.",
    )
    @app_commands.describe(meme="The meme to send.")
    async def meme(self, interaction: Interaction[Client], meme: str) -> None:
        """Send a meme of your choosing to the current channel."""

        if meme not in self._names:
            await interaction.response.send_message(Meme._MISSING, ephemeral=True)
            return

        index: int = self._names.index(meme)
        file: File = File(self._memes[index])

        _LOGGER.info("Sent meme %s for %s", meme, interaction.user.name)

        await interaction.response.send_message(file=file)

    @meme.autocomplete("meme")
    async def meme_autocomplete(
        self,
        _: Interaction[Client],
        current: str,
    ) -> list[Choice[str]]:
        """Use a fuzzy search to generate meme suggestions."""
        if not current:
            return [Choice(name=name, value=name) for name in self._names[:5]]
        return [
            Choice(name=name, value=name)
            for name, _ in process.extract(current, self._names, limit=5)
        ]


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(Meme(), DISCORD.main_guild_id)
