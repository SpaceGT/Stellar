"""Wraps the embed used for ship rescue tasks."""

import math
import re
from dataclasses import dataclass
from typing import TypeVar

from discord import Colour
from discord import Embed as DiscordEmbed

from common.tasks import CarrierRescue, Rescue, ShipRescue

T = TypeVar("T")


@dataclass
class BaseEmbedBuilder:
    """Wraps the embed used for rescue tasks."""

    _WARNING_DISTANCE = 30000

    client_id: int
    system: str
    distance: float
    image_url: str

    @staticmethod
    def from_base_rescue(rescue: Rescue, image_url: str) -> "BaseEmbedBuilder":
        """Create an instance from a Rescue Task object."""
        assert rescue.system.location

        return BaseEmbedBuilder(
            client_id=rescue.client,
            system=rescue.system.name,
            distance=rescue.system.location.magnitude,
            image_url=image_url,
        )

    @staticmethod
    def from_base_embed(embed: DiscordEmbed, image_url: str = "") -> "BaseEmbedBuilder":
        """Create an instance from an existing Rescue embed."""

        client_id = BaseEmbedBuilder._search_embed(embed, "", r"Client: <@(\d+)>", int)
        system = BaseEmbedBuilder._search_embed(
            embed, "Destination", r"System: \[(.+)\]", str
        )
        distance = BaseEmbedBuilder._search_embed(
            embed, "Travel", r"Distance: \[(.+)ly\]", float
        )

        url = image_url or embed.thumbnail.url or None

        if url is None:
            raise ValueError("Missing image URL")

        return BaseEmbedBuilder(
            client_id=client_id,
            system=system,
            distance=distance,
            image_url=url,
        )

    @staticmethod
    def _search_embed(
        embed: DiscordEmbed, field_name: str, regex: str, type_: type[T]
    ) -> T:

        if field_name == "":
            target = embed.description

        else:
            target = next(
                iter(field for field in embed.fields if field.name == field_name)
            ).value

        if target is None:
            raise ValueError

        search = re.search(regex, target)
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
        spansh_url = "https://spansh.co.uk/fleet-carrier"

        embed = (
            DiscordEmbed(
                description=f"Client: <@{self.client_id}>\n",
                colour=Colour.blue(),
            )
            .add_field(
                name="Destination",
                value=(
                    f"System: [{self.system}](<https://www.edsm.net/en/system/id//name"
                    + f"?systemName={self.system.replace(' ', '+')}>)\n"
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

        if self.distance >= BaseEmbedBuilder._WARNING_DISTANCE:
            embed.set_footer(text="(Planning is heavily advised)")

        return embed


class ShipEmbedBuilder(BaseEmbedBuilder):
    """Wraps the embed used for ship rescue tasks."""

    @staticmethod
    def from_rescue(rescue: ShipRescue, image_url: str) -> "ShipEmbedBuilder":
        """Create an instance from a Rescue Task object."""
        base = super(ShipEmbedBuilder, ShipEmbedBuilder).from_base_rescue(
            rescue, image_url
        )

        return ShipEmbedBuilder(
            client_id=base.client_id,
            system=base.system,
            distance=base.distance,
            image_url=base.image_url,
        )

    @staticmethod
    def from_embed(embed: DiscordEmbed, image_url: str = "") -> "ShipEmbedBuilder":
        """Create an instance from an existing Rescue embed."""
        base = super(ShipEmbedBuilder, ShipEmbedBuilder).from_base_embed(
            embed, image_url
        )

        return ShipEmbedBuilder(
            client_id=base.client_id,
            system=base.system,
            distance=base.distance,
            image_url=base.image_url,
        )


@dataclass
class CarrierEmbedBuilder(BaseEmbedBuilder):
    """Wraps the embed used for carrier rescue tasks."""

    tritium: int

    @staticmethod
    def from_rescue(rescue: CarrierRescue, image_url: str) -> "CarrierEmbedBuilder":
        """Create an instance from a Rescue Task object."""
        base = super(CarrierEmbedBuilder, CarrierEmbedBuilder).from_base_rescue(
            rescue, image_url
        )

        return CarrierEmbedBuilder(
            client_id=base.client_id,
            system=base.system,
            distance=base.distance,
            image_url=base.image_url,
            tritium=rescue.tritium,
        )

    @staticmethod
    def from_embed(embed: DiscordEmbed, image_url: str = "") -> "CarrierEmbedBuilder":
        """Create an instance from an existing Rescue embed."""

        base = super(CarrierEmbedBuilder, CarrierEmbedBuilder).from_base_embed(
            embed, image_url
        )
        tritium = super(CarrierEmbedBuilder, CarrierEmbedBuilder)._search_embed(
            embed, "", r"Tritium: \[(.*?)t\]", int
        )

        return CarrierEmbedBuilder(
            client_id=base.client_id,
            system=base.system,
            tritium=tritium,
            distance=base.distance,
            image_url=base.image_url,
        )

    @property
    def embed(self) -> DiscordEmbed:
        """Create an embed based on the current configuration."""
        tritium_url = "https://inara.cz/elite/commodities/?pi1=1&pa1[]=10269"

        embed = super().embed
        assert embed.description
        embed.description += f"Tritium: [{self.tritium:,}t](<{tritium_url}>)"

        return embed
