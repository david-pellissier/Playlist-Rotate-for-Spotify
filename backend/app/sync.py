import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Album, Artist, Settings, Track, utcnow
from .spotify import parse_release_date, spotify

log = logging.getLogger(__name__)

RESYNC_AFTER = timedelta(hours=1)


def known_artists(session: Session, names: list[str]) -> tuple[list[Artist], list[str]]:
    by_name = {artist.name.casefold(): artist for artist in session.scalars(select(Artist))}
    artists = [by_name[name.casefold()] for name in names if name.casefold() in by_name]
    missing = [name for name in names if name.casefold() not in by_name]
    return list(dict.fromkeys(artists)), missing


async def resolve_artists(session: Session, names: list[str]) -> tuple[list[Artist], list[str]]:
    _, unknown = known_artists(session, names)
    found = await asyncio.gather(*(spotify.find_artist(name) for name in unknown))

    for name, data in zip(unknown, found):
        if data is None:
            log.error("No exact Spotify match for artist %r", name)
        elif session.get(Artist, data["id"]) is None:
            session.add(Artist(id=data["id"], name=data["name"]))
    session.commit()
    return known_artists(session, names)


async def sync_artists(session: Session, artists: list[Artist]) -> None:
    now = utcnow()
    stale = [artist for artist in artists if not artist.synced_at or now - artist.synced_at > RESYNC_AFTER]
    if not stale:
        return

    lookback = timedelta(days=session.get(Settings, 1).refresh_lookback_days)
    album_lists = await asyncio.gather(*(
        spotify.artist_albums(artist.id, (artist.synced_at - lookback).date() if artist.synced_at else None)
        for artist in stale
    ))

    fetched_ids = [data["id"] for albums in album_lists for data in albums]
    known_albums = set(session.scalars(select(Album.id).where(Album.id.in_(fetched_ids))))
    new_albums = {}
    for artist, albums in zip(stale, album_lists):
        for data in albums:
            if data["id"] not in known_albums and data["id"] not in new_albums:
                new_albums[data["id"]] = (artist, data)

    track_lists = await asyncio.gather(*(spotify.album_tracks(album_id) for album_id in new_albums))

    seen_tracks = set()
    for (artist, data), tracks in zip(new_albums.values(), track_lists):
        tracks = [t for t in tracks if t.get("id") and t["id"] not in seen_tracks]
        seen_tracks.update(t["id"] for t in tracks)
        album = Album(
            id=data["id"],
            artist_id=artist.id,
            name=data["name"],
            album_type=data["album_type"],
            release_date=parse_release_date(data["release_date"]),
            image_url=data["images"][-1]["url"] if data["images"] else None,
        )
        album.tracks = [
            Track(
                id=track["id"],
                name=track["name"],
                duration_ms=track["duration_ms"],
                disc_number=track["disc_number"],
                track_number=track["track_number"],
                artist_ids=[a["id"] for a in track["artists"]],
            )
            for track in tracks
        ]
        session.add(album)

    for artist in stale:
        artist.synced_at = now
    session.commit()
    log.info("Synced %d artists, %d new albums", len(stale), len(new_albums))
