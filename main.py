"""Build a Spotify playlist of top tracks for every artist with N+ monthly listeners.

Pipeline:
  1. Scrape Kworb's monthly-listeners leaderboard, filter to >= threshold.
  2. For each artist, resolve to a Spotify artist ID via search.
  3. Fetch the artist's top 5 tracks.
  4. Create a new playlist on the authenticated user and add all tracks.

Spotify's Web API does not expose monthly listener counts, so the threshold
filter is applied against Kworb's data, then the Spotify API is used only
for artist lookup, top tracks, and playlist creation.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from dotenv import load_dotenv

import kworb
import spotify


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-listeners",
        type=int,
        default=10_000_000,
        help="Monthly-listener threshold (default: 10000000)",
    )
    parser.add_argument(
        "--tracks-per-artist",
        type=int,
        default=5,
        help="Top tracks to include per artist (default: 5)",
    )
    parser.add_argument(
        "--market",
        default="US",
        help="ISO market code for top-track ranking (default: US)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Playlist name (default: auto-generated from threshold and date)",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Create the playlist as public (default: private)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of artists processed (useful for testing)",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    threshold_m = args.min_listeners // 1_000_000
    print(f"Fetching Kworb leaderboard (>= {args.min_listeners:,} monthly listeners)...")
    listings = kworb.fetch_listings(min_listeners=args.min_listeners)
    if args.limit is not None:
        listings = listings[: args.limit]
    print(f"  {len(listings)} artist(s) above threshold")

    if not listings:
        print("Nothing to do.", file=sys.stderr)
        return 1

    client = spotify.make_client()

    track_uris: list[str] = []
    matched = 0
    missing: list[str] = []
    for i, listing in enumerate(listings, 1):
        artist = spotify.find_artist(client, listing.name)
        if artist is None:
            missing.append(listing.name)
            print(f"  [{i}/{len(listings)}] {listing.name}: NOT FOUND")
            continue

        uris = spotify.top_track_uris(
            client,
            artist.id,
            market=args.market,
            limit=args.tracks_per_artist,
        )
        track_uris.extend(uris)
        matched += 1
        print(f"  [{i}/{len(listings)}] {artist.name}: +{len(uris)} tracks")

    if not track_uris:
        print("No tracks resolved; aborting playlist creation.", file=sys.stderr)
        return 1

    name = args.name or f"Top 5 of {threshold_m}M+ artists ({date.today():%Y-%m-%d})"
    description = (
        f"Top {args.tracks_per_artist} tracks from each Spotify artist with "
        f">= {args.min_listeners:,} monthly listeners (per Kworb). "
        f"Generated {date.today():%Y-%m-%d}."
    )
    print(f"Creating playlist '{name}' ({len(track_uris)} tracks)...")
    playlist_id = spotify.create_playlist(
        client, name=name, description=description, public=args.public
    )
    spotify.add_tracks(client, playlist_id, track_uris)

    print(f"Done. Playlist id: {playlist_id}")
    print(f"  matched: {matched}/{len(listings)} artists")
    if missing:
        print(f"  unresolved: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
