"""Scrape Kworb's Spotify monthly listeners leaderboard.

Kworb publishes a regularly-updated table of Spotify artists ranked by
monthly listeners at https://kworb.net/spotify/listeners.html. The table
columns are: #, Artist, Listeners, Daily +/-, Peak, PkListeners. The
artist cell contains a link of the form ``artist/<spotify_id>_songs.html``,
so we can extract the Spotify artist ID directly and skip a name-based
search.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

KWORB_URL = "https://kworb.net/spotify/listeners.html"
USER_AGENT = (
    "Mozilla/5.0 (compatible; spotify-disc/1.0; "
    "+https://github.com/night4g/spotify-disc)"
)
ARTIST_HREF_RE = re.compile(r"^artist/([A-Za-z0-9]+)(?:_songs)?\.html$")


@dataclass(frozen=True)
class ArtistListing:
    name: str
    spotify_id: str
    monthly_listeners: int


def fetch_listings(min_listeners: int = 10_000_000) -> list[ArtistListing]:
    """Return artists from Kworb with at least ``min_listeners`` monthly listeners.

    Each row is matched by finding the artist link (``artist/<id>...html``).
    The Spotify ID is extracted from the href; the listener count is the
    third ``<td>`` in the row. Results are sorted descending by listeners.
    """
    response = requests.get(
        KWORB_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    listings: list[ArtistListing] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        match = ARTIST_HREF_RE.match(link["href"])
        if not match:
            continue
        spotify_id = match.group(1)
        if spotify_id in seen:
            continue

        row = link.find_parent("tr")
        if row is None:
            continue
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        listeners_text = cells[2].get_text(strip=True).replace(",", "")
        if not listeners_text.isdigit():
            continue

        listeners = int(listeners_text)
        if listeners < min_listeners:
            continue

        seen.add(spotify_id)
        listings.append(
            ArtistListing(
                name=link.get_text(strip=True),
                spotify_id=spotify_id,
                monthly_listeners=listeners,
            )
        )

    listings.sort(key=lambda l: l.monthly_listeners, reverse=True)
    return listings
