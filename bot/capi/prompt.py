"""Prompt shown to users when setting up CAPI."""

import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord import Client
from discord.ui import Modal, TextInput

from bot.core import CLIENT
from common.capi import CapiData
from common.depots import Carrier
from common.enums import Service
from external.capi import auth
from services import CAPI_SERVICE, CAPI_WORKER, DEPOT_SERVICE
from services.capi.worker import _INTERVAL
from settings import CAPI

InternalCarriers = list[tuple[CapiData, Carrier]]
ExternalCarriers = list[CapiData]

_LOGGER = logging.getLogger(__name__)
_START_DATE = datetime.now(timezone.utc)

_SYNCING = """
# :link: Frontier Companion API :link:
**System:**  `Syncing`
**Capacity:**  `Syncing`
**Tritium:**  `Syncing`
**Update:**  `In Progress`
"""


def _error_message() -> str:
    assert CLIENT.application
    message = (
        "# :link: Frontier Companion API :link:\n"
        + "An error occurred whilst linking your account.\n"
        + f"- If you own Elite on `{Service.EPIC}` please run it before you re-auth.\n"
        + "- Do not re-run `/capi` whilst authorising your account.\n"
        + f"- Try again later in case this is a `{Service.FRONTIER}` issue.\n"
        + f"Feel free to contact {CLIENT.application.owner.mention} for assistance!"
    )
    return message


def get_carriers(discord_id: int) -> tuple[InternalCarriers, ExternalCarriers]:
    """Find all carriers owned by a user."""
    internal: InternalCarriers = []
    external: ExternalCarriers = []

    for info in CAPI_SERVICE.get_data():
        if info.discord_id != discord_id:
            continue

        if not info.carrier:
            continue

        carrier = DEPOT_SERVICE.carriers.find(callsign=info.carrier)
        if carrier:
            internal.append((info, carrier))
        else:
            external.append(info)

    return internal, external


def capi_overview(discord_id: int) -> str:
    """Show connected carriers owned by a user using a message."""
    message = ["# :link: Frontier Companion API :link:"]
    internal, external = get_carriers(discord_id)

    for info, carrier in internal:
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

    if internal and external:
        message.append("## :cloud: External :cloud:")

    for info in external:
        carrier_message = f"`{info.commander}` - "

        if info.carrier:
            carrier_message += f"`[{info.carrier}]`"
        else:
            carrier_message += f"`No Carrier`"

        if not info.access_token:
            carrier_message += f"  (Expired)"

        # Store external carriers as full objects in the future.
        # Currently only their update time is stored and this is fetched
        # from the worker's internal cache (has some quirks).
        elif info.carrier and (datetime.now(timezone.utc) - _START_DATE) > _INTERVAL:
            last_update = CAPI_WORKER._cache[info.carrier]
            carrier_message += f"  <t:{int(last_update.timestamp())}:R>"

        message.append(carrier_message)

    if not internal:
        assert CLIENT.application
        footer = [
            "",
            ":cloud: Market synced with third party apps.",
            f":tools: Contact {CLIENT.application.owner.mention} to delist an account.",
        ]
        message.extend(footer)

    return "\n".join(message)


async def _auth_capi(
    interaction: discord.Interaction[Client], auth_code: str, verifier: str
) -> None:
    success = await CAPI_SERVICE.auth_account(
        auth_code, verifier, interaction.user.id, sync=True
    )

    if success:
        message = capi_overview(interaction.user.id)
        await interaction.edit_original_response(content=message, view=None)

    else:
        message = _error_message()
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
