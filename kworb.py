"""Scrape Kworb's Spotify monthly listeners leaderboard.

Kworb publishes a regularly-updated table of Spotify artists ranked by
monthly listeners at https://kworb.net/spotify/listeners.html. The page
is a single static HTML table whose first column is the artist name and
whose third column is the monthly listener count.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

KWORB_URL = "https://kworb.net/spotify/listeners.html"
USER_AGENT = (
    "Mozilla/5.0 (compatible; spotify-disc/1.0; "
    "+https://github.com/night4g/spotify-disc)"
)


@dataclass(frozen=True)
class ArtistListing:
    name: str
    monthly_listeners: int


def fetch_listings(min_listeners: int = 10_000_000) -> list[ArtistListing]:
    """Return artists from Kworb with at least ``min_listeners`` monthly listeners.

    The list is returned in Kworb's display order (descending by monthly
    listeners), so callers can simply iterate.
    """
    response = requests.get(
        KWORB_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")
    if table is None:
        raise RuntimeError("Could not find leaderboard table on Kworb page")

    listings: list[ArtistListing] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        name = cells[0].get_text(strip=True)
        listeners_text = cells[2].get_text(strip=True).replace(",", "")
        if not listeners_text.isdigit():
            continue

        listeners = int(listeners_text)
        if listeners < min_listeners:
            # Table is sorted descending — once we drop below the threshold
            # we can stop scanning.
            break

        listings.append(ArtistListing(name=name, monthly_listeners=listeners))

    return listings
