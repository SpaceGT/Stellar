"""Wraps the embed used for restock tasks."""

import math
import re
from dataclasses import dataclass
from typing import TypeVar

from discord import Colour
from discord import Embed as DiscordEmbed

from common.depots import Carrier

T = TypeVar("T")


@dataclass
class EmbedBuilder:
    """Wraps the embed used for restock tasks."""

    _WARNING_DISTANCE = 30000

    depot: str
    depot_url: str
    system: str
    stock: int
    allocated: int
    owner_id: int
    delivered: int
    target: int
    distance: float
    image_url: str

    @staticmethod
    def from_carrier(carrier: Carrier, image_url: str) -> "EmbedBuilder":
        """Create an instance from a Carrier object."""
        assert carrier.tritium
        assert carrier.system.location

        return EmbedBuilder(
            depot=str(carrier),
            depot_url=carrier.inara_url,
            system=carrier.system.name,
            stock=carrier.tritium.stock.quantity,
            allocated=carrier.allocated_space,
            owner_id=carrier.owner_discord_id,
            delivered=0,
            target=carrier.allocated_space - carrier.tritium.stock.quantity,
            distance=carrier.system.location.magnitude,
            image_url=image_url,
        )

    @staticmethod
    def from_embed(embed: DiscordEmbed, image_url: str = "") -> "EmbedBuilder":
        """Create an instance from an existing Restock embed."""

        depot = EmbedBuilder._search_embed(
            embed, "Destination", r"Depot: \[(.+)\]", str
        )
        depot_url = EmbedBuilder._search_embed(
            embed, "Destination", r"Depot:.+\(<(.+)>\)", str
        )
        system = EmbedBuilder._search_embed(
            embed, "Destination", r"System: \[(.+)\]", str
        )
        stock = EmbedBuilder._search_embed(
            embed, "Destination", r"Stock: \[(.*?)t\]", int
        )
        allocated = EmbedBuilder._search_embed(
            embed, "Destination", r"Stock:.+\/ \[(.*?)t\]", int
        )
        owner_id = EmbedBuilder._search_embed(
            embed, "Destination", r"Owner: <@(\d+)>", int
        )
        delivered = EmbedBuilder._search_embed(
            embed, "Progress", r"Delivered: \[(.*?)t\]", int
        )
        target = EmbedBuilder._search_embed(
            embed, "Progress", r"Delivered:.+\/ \[(.*?)t\]", int
        )
        distance = EmbedBuilder._search_embed(
            embed, "Travel", r"Distance: \[(.+)ly\]", float
        )

        url = image_url or embed.thumbnail.url or None

        if url is None:
            raise ValueError("Missing image URL")

        return EmbedBuilder(
            depot=depot,
            depot_url=depot_url,
            system=system,
            stock=stock,
            allocated=allocated,
            owner_id=owner_id,
            delivered=delivered,
            target=target,
            distance=distance,
            image_url=url,
        )

    @staticmethod
    def _search_embed(
        embed: DiscordEmbed, field_name: str, regex: str, type_: type[T]
    ) -> T:
        target = next(
            iter([field for field in embed.fields if field.name == field_name]), None
        )

        if target is None or target.value is None:
            raise ValueError

        search = re.search(regex, target.value)
        if search is None:
            raise ValueError

        data = str(search.group(1))

        if type_ is int:
            return int(data.replace(",", ""))  # type: ignore [return-value]

        if type_ is float:
            return float(data.replace(",", ""))  # type: ignore [return-value]

        if type_ is str:
            return data  # type: ignore [return-value]

        raise TypeError

    @property
    def embed(self) -> DiscordEmbed:
        """Create an embed based on the current configuration."""

        tritium_url = "https://inara.cz/elite/commodities/?pi1=1&pa1[]=10269"
        spansh_url = "https://spansh.co.uk/fleet-carrier"

        embed = (
            DiscordEmbed(colour=Colour.blue())
            .add_field(
                name="Destination",
                value=(
                    f"Depot: [{self.depot}](<{self.depot_url}>)\n"
                    + f"System: [{self.system}](<https://www.edsm.net/en/system/id//name"
                    + f"?systemName={self.system.replace(' ', '+')}>)\n"
                    + f"Stock: [{self.stock:,}t](<{tritium_url}>) / "
                    + f"[{self.allocated:,}t](<{tritium_url}>)\n"
                    + f"Owner: <@{self.owner_id}>"
                ),
                inline=False,
            )
            .add_field(
                name="Progress",
                value=(
                    f"Delivered: [{self.delivered:,}t](<{tritium_url}>) / "
                    + f"[{self.target:,}t](<{tritium_url}>)"
                ),
                inline=False,
            )
            .add_field(
                name="Travel",
                value=(
                    f"Distance: [{self.distance:,.0f}ly](<{spansh_url}>)\n"
                    + f"Jumps: [{math.ceil(self.distance/500):,}](<{spansh_url})"
                ),
                inline=False,
            )
            .set_thumbnail(url=self.image_url)
        )

        if self.distance >= EmbedBuilder._WARNING_DISTANCE:
            embed.set_footer(text="(Planning is heavily advised)")

        return embed
