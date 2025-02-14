"""Creates buttons used to manage CAPI status."""

import copy

from discord import ButtonStyle, Client, Interaction
from discord.ui import Button, View

from .prompt import Prompt


class CapiView(View):
    """Creates buttons used to manage CAPI status."""

    connect: Button = Button(
        label="Connect",
        style=ButtonStyle.green,
        emoji="\U0001f4cb",
    )

    refresh: Button = Button(
        label="Refresh",
        style=ButtonStyle.grey,
        emoji="\U0001f504",
        url="https://auth.frontierstore.net/",
    )

    def __init__(self, prompt: Prompt, auth_url: str) -> None:
        super().__init__(timeout=180)
        self.prompt = prompt

        authorise: Button = Button(
            label="Authorise",
            style=ButtonStyle.blurple,
            emoji="\U0001f510",
            url=auth_url,
        )
        self.add_item(authorise)

        connect: Button = copy.deepcopy(CapiView.connect)
        setattr(connect, "callback", self.url_prompt)
        self.add_item(connect)

        refresh: Button = copy.deepcopy(CapiView.refresh)
        self.add_item(refresh)

    async def url_prompt(self, interaction: Interaction[Client]) -> None:
        """Open a prompt for entering the URL with the CAPI code."""

        # Disable multiple attempts (url must be regenerated)
        for child in self.children:
            if isinstance(child, Button):
                child.disabled = True

        await interaction.response.send_modal(self.prompt)
        await interaction.edit_original_response(view=self)
