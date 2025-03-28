"""Allows scraping limited data from INARA"""

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib import parse

from aiohttp import ClientSession
from bs4 import BeautifulSoup, Tag

from common import Good
from settings import SOFTWARE

_TIMEOUT = 60
_URL = "https://inara.cz/"


async def _request(url: str) -> str:
    headers = {"User-Agent": SOFTWARE.user_agent}

    async with (
        ClientSession(raise_for_status=True) as session,
        session.get(f"{_URL}{url}", headers=headers, timeout=_TIMEOUT) as response,
    ):
        content = await response.text()

    return content


async def _market(inara_id: int) -> dict[str, Any]:
    response = await _request(f"elite/station-market/{inara_id}/")
    soup = BeautifulSoup(response, "lxml")

    # Scrape system info
    system = soup.find("a", href=re.compile(r"/elite/starsystem/\d+/"))
    if system is None:
        raise ValueError("Could not find System.")

    # Scrape update time info
    update_text = soup.find("div", text="Market update")
    if update_text is None:
        raise ValueError("Could not find Market Update")

    update_time = update_text.find_next_sibling("div")
    if not update_time:
        raise ValueError("Could not find Market Update")

    update_date = update_time.find("span")
    if not update_date:
        raise ValueError("Could not find Market Update")

    assert not isinstance(update_date, int)
    update = datetime.strptime(
        update_date.text.strip("()"), "%d %b %Y, %I:%M%p"
    ).replace(tzinfo=timezone.utc)

    # Handle markets with no data
    data: dict[str, Any] = {"system": system.text, "update": update, "commodities": []}

    if soup.find(text="No market data known."):
        return data

    # Scrape market data
    tables: list[Tag] = soup.find_all("table")
    if len(tables) != 1:
        raise ValueError("Could not find table.")

    table_body = tables[0].find("tbody")
    assert isinstance(table_body, Tag)  # Table will always have a tbody

    rows: list[Tag] = table_body.find_all("tr")
    rows = [row for row in rows if not row.has_attr("class")]

    if not rows:
        raise ValueError("Could not find Market Data.")

    for row in rows:
        cells: list[Tag] = row.find_all("td")

        assert len(cells) == 5

        data["commodities"] += [
            {
                "name": cells[0].text,
                "sellPrice": int(cells[1].attrs.get("data-order", 0)),
                "demand": int(cells[2].attrs.get("data-order", 0)),
                "buyPrice": int(cells[3].attrs.get("data-order", 0)),
                "stock": int(cells[4].attrs.get("data-order", 0)),
            }
        ]

    return data


async def overview(inara_id: int) -> tuple[list[Good], str, datetime]:
    """
    Scrapes (relatively little) market info from an INARA ID.
    Use this over EDSM for carriers that are ONLY updated on INARA!
    """
    response = await _market(inara_id)

    market = [
        Good(
            commodity["name"],
            {
                "price": commodity["buyPrice"],
                "quantity": commodity["stock"],
            },
            {
                "price": commodity["sellPrice"],
                "quantity": commodity["demand"],
            },
        )
        for commodity in response["commodities"]
    ]

    return market, response["system"], response["update"]


async def search(callsign: str) -> tuple[str, str, int] | None:
    """
    Search for a carrier by callsign.
    Returns (name, system and ID) or None if unregistered.
    """

    if not re.match(r"^[A-Z0-9]{3}-[A-Z0-9]{3}$", callsign, re.MULTILINE):
        return None

    response = await _request(
        f"sites/elite/ajaxsearch.php?type=GlobalSearch&term={callsign}"
    )

    for data in json.loads(response):
        if data["value"] == "[submitform]":
            continue

        name, system = data["value"].split(" | ")

        if not re.search(r" \([A-Z0-9]{3}-[A-Z0-9]{3}\)$", name, re.MULTILINE):
            continue

        display_name = name[:-10]

        soup = BeautifulSoup(data["label"], "lxml")
        link = soup.find("a").get("href")
        assert isinstance(link, str)

        parsed = parse.urlparse(link)
        parts = parsed.path.split("/")
        station_id = int(parts[3])

        return display_name, system, station_id

    return None
