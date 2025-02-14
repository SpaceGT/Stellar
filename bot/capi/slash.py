"""Allows users setup Companion API integration."""

from discord import Client, Interaction, app_commands
from discord.ext import commands

from bot.core import CLIENT
from common.enums import State
from external.capi import auth
from services import CAPI_SERVICE, DEPOT_SERVICE
from settings import CAPI, DISCORD, SOFTWARE

from .prompt import Prompt, carrier_overview
from .view import CapiView

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
Around 25 days after connecting you will need to re-authorise `{SOFTWARE.name}`.
The recommended way is clicking `Refresh` and logging in.
This site can be used to revoke {SOFTWARE.name}'s access at any time should you choose.
"""


class Capi(commands.Cog):
    """Help users setup the Companion API."""

    @app_commands.command(  # type: ignore [arg-type]
        name="capi",
        description=f"Connect {SOFTWARE.name} to your Frontier account.",
    )
    async def capi(self, interaction: Interaction[Client]) -> None:
        """Help users setup the Companion API."""
        assert interaction.client.application
        auth_data = auth.oauth_data()

        prompt = Prompt(auth_data["verifier"])
        view = CapiView(prompt, auth_data["url"])

        depots = [
            carrier
            for carrier in DEPOT_SERVICE.carriers
            if carrier.owner_discord_id == interaction.user.id
            and CAPI_SERVICE.get_state(carrier.name) != State.UNLISTED
        ]

        if depots:
            message = carrier_overview(
                interaction.user.id, interaction.client.application.owner.mention
            )
        else:
            message = _SUMMARY

        await interaction.response.send_message(
            message,
            ephemeral=True,
            view=view,
        )


def main() -> None:
    """Load the cog into the client."""
    CLIENT.load_cog(Capi(), DISCORD.main_guild_id)
