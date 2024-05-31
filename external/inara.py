"""Allows scraping limited data from INARA"""

import re
from datetime import datetime, timezone
from typing import Any

from aiohttp import ClientSession
from bs4 import BeautifulSoup, Tag

from common import Good
from settings import SOFTWARE

_TIMEOUT = 60
_URL = "https://inara.cz/elite"


async def _request(url: str) -> BeautifulSoup:
    headers = {"User-Agent": SOFTWARE.user_agent}

    async with ClientSession() as session:
        async with session.get(
            f"{_URL}{url}", headers=headers, timeout=_TIMEOUT
        ) as response:
            if response.status != 200:
                response.raise_for_status()

            content = await response.text()

    return BeautifulSoup(content, "lxml")


async def _market(inara_id: int) -> dict[str, Any]:
    soup = await _request(f"/station-market/{inara_id}/")

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
