"""Prompt shown to users when setting up CAPI."""

import asyncio
import logging

import discord
from discord import Client
from discord.ui import Modal, TextInput

from common.enums import Service
from external.capi import auth
from services import CAPI_SERVICE, DEPOT_SERVICE
from settings import CAPI

_LOGGER = logging.getLogger(__name__)

_SYNCING = """
# :link: Frontier Companion API :link:
**System:**  `Syncing`
**Capacity:**  `Syncing`
**Tritium:**  `Syncing`
**Update:**  `In Progress`
"""


def _error_message(owner_mention: str) -> str:
    message = (
        "# :link: Frontier Companion API :link:\n"
        + "An error occurred whilst linking your account.\n"
        + f"If you own Elite on `{Service.EPIC}` please run it before you re-auth.\n"
        + f"Feel free to contact {owner_mention} for assistance!"
    )
    return message


def carrier_overview(discord_id: int, owner_mention: str) -> str:
    """Creates an overview message for a user's connected carriers"""
    message = ["# :link: Frontier Companion API :link:"]

    for carrier in DEPOT_SERVICE.carriers:
        if carrier.owner_discord_id != discord_id:
            continue

        # Use `get_state` in the future.
        # You will need to store the commander name as a carrier field.
        info = CAPI_SERVICE.get_data().find_carrier(carrier.name)
        if not info:
            continue

        carrier_message = [f"## `{info.commander}` - `{carrier}`"]

        if not info.access_token:
            carrier_message[0] += " (Expired)"

        carrier_message += [
            f"**System:**  `{carrier.system}`",
            f"**Capacity:**  `{carrier.allocated_space:,}t`",
        ]

        tritium: str
        if carrier.tritium and not carrier.tritium.demand.quantity:
            tritium = f"**Tritium:**  `{carrier.tritium.stock.quantity:,}t`"
        else:
            tritium = "**Tritium:**  `Not Selling`"

        carrier_message += [
            tritium,
            f"**Update:**  <t:{int(carrier.last_update.timestamp())}:R>",
        ]

        message.extend(carrier_message)

    if len(message) == 1:
        message += [
            ":white_check_mark: Frontier account linked successfully.",
            ":cloud: Market synced with third party apps.",
            f":ship: Contact {owner_mention} to become a depot.",
        ]

    return "\n".join(message)


async def _auth_capi(
    interaction: discord.Interaction[Client], auth_code: str, verifier: str
) -> None:
    assert interaction.client.application
    owner_mention = interaction.client.application.owner.mention

    success = await CAPI_SERVICE.auth_account(
        auth_code, verifier, interaction.user.id, sync=True
    )

    if success:
        message = carrier_overview(interaction.user.id, owner_mention)
        await interaction.edit_original_response(content=message, view=None)

    else:
        message = _error_message(owner_mention)
        await interaction.edit_original_response(content=message, view=None)


class Prompt(Modal, title="Enter Copied Link"):
    """Prompt shown to users when setting up CAPI."""

    url: TextInput = TextInput(label="Link", placeholder=f"{CAPI.redirect_url}...")

    def __init__(self, verifier: str) -> None:
        super().__init__(timeout=None)
        self.verifier = verifier

    async def on_submit(  # pylint: disable=arguments-differ
        self, interaction: discord.Interaction[Client]
    ) -> None:
        _LOGGER.info("Recieved CAPI URL from %s", interaction.user.name)
        auth_code = auth.get_auth_code(self.url.value)

        if auth_code:
            message = _SYNCING
            asyncio.create_task(
                _auth_capi(interaction, auth_code, self.verifier),
                name=f"capi-{interaction.user.name}",
            )

        else:
            assert interaction.client.application
            message = _error_message(interaction.client.application.owner.mention)

        await interaction.response.edit_message(content=message, view=None)
