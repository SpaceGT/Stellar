"""Allows users setup Companion API integration."""

import json
import logging
from io import BytesIO
from itertools import chain
from typing import Any

from discord import Client, File, Interaction, app_commands
from discord.app_commands import Choice
from discord.ext import commands
from thefuzz import process

from bot.core import CLIENT
from external.capi import AuthEndpoint, QueryEndpoint, auth, query
from services import CAPI_SERVICE
from settings import CAPI, DISCORD, SOFTWARE, TIMINGS

from .prompt import Prompt, capi_overview, get_carriers
from .view import CapiView

_LOGGER = logging.getLogger(__name__)

_SUMMARY = f"""
# :link: Frontier Companion API :link:
## History :clock:
The Companion API was originally created for an official app on IOS (which has succumbed to bitrot)
Enough developers had figured and utilized the API for Frontier Developments to continue supporting it.
## {SOFTWARE.name} :robot:
{SOFTWARE.name} will use the API to periodically fetch your carrier's market data.
This allows for tritium levels to be kept updated without relying on other commanders.
It also sends EDDN updates to keep your carrier in sync with other third party tools.
Deployment information (such as the current system or maximum tritium capacity) are also fetched.
## Setup :tools:
Click on the `Authorise` button.
- Authorise `{CAPI.client_name}` to access your commander.
- You should be redirected to `{CAPI.redirect_url}`.
- Copy the link in the address bar (`Ctrl L`, `Ctrl C`)
Click on the `Connect` button.
- Paste the link you copied into the form.
## Management :clipboard:
Around 25 days after connecting you will need to re-authorise `{SOFTWARE.name}`.""" + (
    f"""
The recommended way is clicking `Refresh` and logging in.
This site can be used to revoke {SOFTWARE.name}'s access at any time should you choose.
"""
    if CAPI.retry_refresh
    else f"""
You will receive reminders to do this every `{TIMINGS.capi_followup.total_seconds() // 3600:.0f}` hours via DM.
"""
)


class Authorise(commands.Cog):
    """Help users setup the Companion API."""

    @app_commands.command(  # type: ignore [arg-type]
        name="capi",
        description=f"Connect {SOFTWARE.name} to your Frontier account.",
    )
    async def capi(self, interaction: Interaction[Client]) -> None:
        """Help users setup the Companion API."""
        _LOGGER.info("Sending CAPI Card to %s", interaction.user.name)

        assert interaction.client.application
        auth_data = auth.oauth_data()

        prompt = Prompt(auth_data["verifier"])
        view = CapiView(prompt, auth_data["url"])

        if any(get_carriers(interaction.user.id)):
            message = capi_overview(interaction.user.id)
        else:
            message = _SUMMARY

        await interaction.response.send_message(
            message,
            ephemeral=True,
            view=view,
        )


class Admin(commands.GroupCog, group_name="capi"):
    """Manually manage CAPI data."""

    @app_commands.command(  # type: ignore [arg-type]
        name="fetch",
        description="Fetch information from CAPI.",
    )
    @app_commands.describe(
        commander="Account to fetch information for.",
        endpoint="Which information is queried.",
    )
    @app_commands.choices(
        endpoint=[
            Choice(name=endpoint, value=endpoint)
            for endpoint in chain(AuthEndpoint, QueryEndpoint)
        ],
    )
    async def fetch(
        self,
        interaction: Interaction[Client],
        commander: str,
        endpoint: Choice[str],
    ) -> None:
        """Fetch information from CAPI."""
        commanders = [data.commander for data in CAPI_SERVICE.get_data()]
        if commander not in commanders:
            await interaction.response.send_message(
                (
                    "## :link: Frontier Companion API :link:\n"
                    + f"No data availible for `{commander}`"
                ),
                ephemeral=True,
            )
            return

        token = await CAPI_SERVICE.get_token(commander)
        if token is None:
            await interaction.response.send_message(
                (
                    "## :link: Frontier Companion API :link:\n"
                    + f"Could not fetch token for `{commander}`"
                ),
                ephemeral=True,
            )
            return

        data: dict[str, Any]
        if endpoint.value in AuthEndpoint:
            data = await auth.request(
                AuthEndpoint(endpoint.value),
                token[0],
            )

        elif endpoint.value in QueryEndpoint:
            data = await query.request(
                QueryEndpoint(endpoint.value),
                token[0],
            )

        else:
            await interaction.response.send_message(
                (
                    "## :link: Frontier Companion API :link:\n"
                    + f"Unknown endpoint `{endpoint}`"
                ),
                ephemeral=True,
            )
            return

        _LOGGER.info(
            "Fetching '%s' endpoint on '%s' for %s",
            endpoint.value,
            commander,
            interaction.user.name,
        )

        pretty_data = json.dumps(data, indent=4)
        with BytesIO(pretty_data.encode("utf-8")) as bytes_io:
            response = (
                "## :link: Frontier Companion API :link:\n"
                + f"Fetched `{endpoint.name}` for `{commander}`"
            )

            file = File(bytes_io, f"capi.json")
            await interaction.response.send_message(response, ephemeral=True, file=file)

    @fetch.autocomplete("commander")
    async def fetch_autocomplete(
        self,
        interaction: Interaction[Client],
        current: str,
    ) -> list[Choice[str]]:
        """Generate suggestions for commanders."""
        commanders = [data.commander for data in CAPI_SERVICE.get_data()]

        if not current:
            return [Choice(name=name, value=name) for name in commanders[:5]]

        return [
            Choice(name=commander, value=commander)
            for commander, _ in process.extract(
                current,
                commanders,
                limit=5,
            )
        ]


def main() -> None:
    """Load the cogs into the client."""
    CLIENT.load_cog(Authorise(), DISCORD.main_guild_id)
    CLIENT.load_cog(Admin(), DISCORD.test_guild_id)
