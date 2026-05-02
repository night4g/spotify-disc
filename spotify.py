"""Thin wrapper around spotipy for the playlist-building flow.

Provides three operations the CLI needs:
  * resolve an artist name to a Spotify artist ID
  * fetch an artist's top tracks
  * create (or replace) a playlist and populate it with track URIs
"""

from __future__ import annotations

from dataclasses import dataclass

import spotipy
from spotipy.oauth2 import SpotifyOAuth

SCOPE = "playlist-modify-private playlist-modify-public"
PLAYLIST_BATCH_SIZE = 100


@dataclass(frozen=True)
class Artist:
    id: str
    name: str


def make_client() -> spotipy.Spotify:
    """Return a spotipy client authenticated for playlist modification.

    Credentials are read from the standard ``SPOTIPY_CLIENT_ID``,
    ``SPOTIPY_CLIENT_SECRET`` and ``SPOTIPY_REDIRECT_URI`` env vars.
    """
    auth_manager = SpotifyOAuth(scope=SCOPE, cache_path=".spotipy_cache")
    return spotipy.Spotify(auth_manager=auth_manager, requests_timeout=30, retries=3)


def find_artist(client: spotipy.Spotify, name: str) -> Artist | None:
    """Resolve an artist name to a Spotify artist via the search endpoint.

    Returns the highest-popularity exact (case-insensitive) name match if one
    exists, otherwise the first search result, otherwise ``None``.
    """
    result = client.search(q=f'artist:"{name}"', type="artist", limit=10)
    items = result.get("artists", {}).get("items", [])
    if not items:
        return None

    target = name.casefold()
    exact = [a for a in items if a["name"].casefold() == target]
    pool = exact or items
    best = max(pool, key=lambda a: a.get("popularity", 0))
    return Artist(id=best["id"], name=best["name"])


def top_track_uris(
    client: spotipy.Spotify,
    artist_id: str,
    market: str = "US",
    limit: int = 5,
) -> list[str]:
    """Return up to ``limit`` top-track URIs for the given artist."""
    response = client.artist_top_tracks(artist_id, country=market)
    tracks = response.get("tracks", [])[:limit]
    return [t["uri"] for t in tracks]


def create_playlist(
    client: spotipy.Spotify,
    name: str,
    description: str,
    public: bool,
) -> str:
    """Create a new playlist on the authenticated user and return its ID."""
    user_id = client.current_user()["id"]
    playlist = client.user_playlist_create(
        user=user_id,
        name=name,
        public=public,
        description=description,
    )
    return playlist["id"]


def add_tracks(client: spotipy.Spotify, playlist_id: str, uris: list[str]) -> None:
    """Add ``uris`` to ``playlist_id``, batching to respect the API limit."""
    for start in range(0, len(uris), PLAYLIST_BATCH_SIZE):
        chunk = uris[start : start + PLAYLIST_BATCH_SIZE]
        client.playlist_add_items(playlist_id, chunk)
