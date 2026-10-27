import logging
from datetime import timedelta
from itertools import batched

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Album, Artist, Settings, Track, utcnow
from .progress import Progress
from .spotify import gather_all, parse_release_date, spotify

log = logging.getLogger(__name__)

RESYNC_AFTER = timedelta(hours=1)
ALBUM_BATCH = 20


def known_artists(session: Session, names: list[str]) -> tuple[list[Artist], list[str]]:
    by_name = {artist.name.casefold(): artist for artist in session.scalars(select(Artist))}
    artists = [by_name[name.casefold()] for name in names if name.casefold() in by_name]
    missing = [name for name in names if name.casefold() not in by_name]
    return list(dict.fromkeys(artists)), missing


async def resolve_artists(session: Session, names: list[str], progress: Progress) -> tuple[list[Artist], list[str]]:
    _, unknown = known_artists(session, names)
    progress.start("Finding artists", len(unknown))
    found = await gather_all(progress.count(spotify.find_artist(name)) for name in unknown)

    for name, data in zip(unknown, found):
        if data is None:
            log.error("No exact Spotify match for artist %r", name)
        elif artist := session.get(Artist, data["id"]):
            artist.name = data["name"]
        else:
            session.add(Artist(id=data["id"], name=data["name"]))
    session.commit()
    return known_artists(session, names)


async def sync_artists(session: Session, artists: list[Artist], progress: Progress) -> None:
    now = utcnow()
    stale = [artist for artist in artists if not artist.synced_at or now - artist.synced_at > RESYNC_AFTER]
    if not stale:
        return

    lookback = timedelta(days=session.get(Settings, 1).refresh_lookback_days)
    progress.start("Updating catalog", len(stale))
    for artist in stale:
        progress.step = f"Updating catalog: {artist.name}"
        new_albums = await _sync_artist(session, artist, lookback)
        artist.synced_at = utcnow()
        session.commit()
        progress.done += 1
        if new_albums:
            log.info("Synced %s: %d new albums", artist.name, new_albums)


async def _sync_artist(session: Session, artist: Artist, lookback: timedelta) -> int:
    released_after = (artist.synced_at - lookback).date() if artist.synced_at else None
    listed = await spotify.artist_albums(artist.id, released_after)
    known = set(session.scalars(select(Album.id).where(Album.id.in_([album["id"] for album in listed]))))
    new_albums = list({album["id"]: album for album in listed if album["id"] not in known}.values())

    for batch in batched(new_albums, ALBUM_BATCH):
        track_lists = await gather_all(spotify.album_tracks(album["id"]) for album in batch)
        track_ids = [track["id"] for tracks in track_lists for track in tracks if track.get("id")]
        seen = set(session.scalars(select(Track.id).where(Track.id.in_(track_ids))))
        for data, tracks in zip(batch, track_lists):
            tracks = [track for track in tracks if track.get("id") and track["id"] not in seen]
            seen.update(track["id"] for track in tracks)
            session.add(_album(artist, data, tracks))
        session.commit()
    return len(new_albums)


def _album(artist: Artist, data: dict, tracks: list[dict]) -> Album:
    return Album(
        id=data["id"],
        artist_id=artist.id,
        name=data["name"],
        album_type=data["album_type"],
        release_date=parse_release_date(data["release_date"]),
        image_url=data["images"][-1]["url"] if data.get("images") else None,
        tracks=[
            Track(
                id=track["id"],
                name=track["name"],
                duration_ms=track["duration_ms"],
                disc_number=track["disc_number"],
                track_number=track["track_number"],
                artist_ids=[a["id"] for a in track["artists"]],
            )
            for track in tracks
        ],
    )
