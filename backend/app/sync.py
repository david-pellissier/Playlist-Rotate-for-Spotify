import logging
from datetime import datetime, timedelta
from itertools import batched

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Album, Artist, Playlist, Settings, Track, utcnow
from .progress import Progress
from .spotify import RateLimitError, SpotifyError, gather_all, parse_release_date, pick_image, spotify

log = logging.getLogger(__name__)

RESYNC_AFTER = timedelta(hours=1)
RETRY_FAILED_AFTER = timedelta(days=1)
ALBUM_BATCH = 20

failed_lookups: dict[str, datetime] = {}


def recently_failed(key: str) -> bool:
    failed_at = failed_lookups.get(key)
    return failed_at is not None and utcnow() - failed_at < RETRY_FAILED_AFTER


async def resolve_artists(session: Session, names: list[str], progress: Progress) -> None:
    known = {name.casefold() for name in session.scalars(select(Artist.name))}
    unknown = [name for name in names if name.casefold() not in known and not recently_failed(name.casefold())]
    progress.start("Finding artists", len(unknown))
    found = await gather_all(progress.count(spotify.find_artist(name)) for name in unknown)

    for name, data in zip(unknown, found):
        if data is None:
            failed_lookups[name.casefold()] = utcnow()
            log.error("No exact Spotify match for artist %r", name)
        elif artist := session.get(Artist, data["id"]):
            artist.name = data["name"]
            artist.image_url = pick_image(data.get("images"))
        else:
            session.add(Artist(id=data["id"], name=data["name"], image_url=pick_image(data.get("images"))))
    session.commit()


def artists_needing_singles(session: Session) -> set[str]:
    playlists = session.scalars(select(Playlist).where(Playlist.albums_only.is_(False))).all()
    names = {name.casefold() for playlist in playlists for name in playlist.artist_names}
    linked = {item_id for playlist in playlists for _, kind, item_id in playlist.links if kind == "artist"}
    return linked | {artist.id for artist in session.scalars(select(Artist)) if artist.name.casefold() in names}


async def sync_artists(session: Session, artists: list[Artist], progress: Progress) -> None:
    now = utcnow()
    wanted = artists_needing_singles(session)
    singles = {artist.id: artist.id in wanted for artist in artists}
    stale = [artist for artist in artists if _needs_sync(artist, now, singles[artist.id])]
    if not stale:
        return

    lookback = timedelta(days=session.get(Settings, 1).refresh_lookback_days)
    progress.start("Updating catalog", len(stale))
    for artist in stale:
        progress.step = f"Updating catalog: {artist.name}"
        if artist.image_url is None:
            await load_image(artist)
            session.commit()
        new_albums = await _sync_artist(session, artist, lookback, singles[artist.id])
        artist.synced_at = utcnow()
        artist.singles_synced = singles[artist.id]
        session.commit()
        progress.done += 1
        if new_albums:
            log.info("Synced %s: %d new albums", artist.name, new_albums)


async def load_image(artist: Artist) -> None:
    try:
        artist.image_url = pick_image((await spotify.artist(artist.id)).get("images"))
    except RateLimitError:
        raise
    except SpotifyError as error:
        log.warning("Could not load the picture of %s: %s", artist.name, error)


def _needs_sync(artist: Artist, now: datetime, with_singles: bool) -> bool:
    if not artist.synced_at or now - artist.synced_at > RESYNC_AFTER:
        return True
    return with_singles and not artist.singles_synced


async def _sync_artist(session: Session, artist: Artist, lookback: timedelta, with_singles: bool) -> int:
    released_after = (artist.synced_at - lookback).date() if artist.synced_at else None
    groups = {"album": released_after}
    if with_singles:
        groups["single"] = released_after if artist.singles_synced else None
    listed = await spotify.artist_albums(artist.id, groups)
    complete = set(
        session.scalars(select(Album.id).where(Album.id.in_([album["id"] for album in listed]), Album.complete))
    )
    new_albums = list({album["id"]: album for album in listed if album["id"] not in complete}.values())

    for batch in batched(new_albums, ALBUM_BATCH):
        track_lists = await gather_all(spotify.album_tracks(album["id"]) for album in batch)
        for data, tracks in zip(batch, track_lists):
            store_album(session, artist, data, tracks)
        session.commit()
    return len(new_albums)


def stored_artist(session: Session, data: dict) -> Artist:
    artist = session.get(Artist, data["id"])
    if artist is None:
        artist = Artist(id=data["id"], name=data["name"])
        session.add(artist)
    return artist


def store_album(session: Session, artist: Artist, data: dict, tracks: list[dict]) -> None:
    track_ids = [track["id"] for track in tracks if track.get("id")]
    stored = set(session.scalars(select(Track.id).where(Track.id.in_(track_ids))))
    new_tracks = [new_track(t) for t in {t["id"]: t for t in tracks if t.get("id") and t["id"] not in stored}.values()]
    album = session.get(Album, data["id"])
    if album is None:
        album = new_album(artist, data)
        session.add(album)
    album.tracks.extend(new_tracks)
    album.complete = True


def new_album(artist: Artist, data: dict, complete: bool = True) -> Album:
    return Album(
        id=data["id"],
        artist_id=artist.id,
        name=data["name"],
        album_type=data["album_type"],
        release_date=parse_release_date(data["release_date"]),
        image_url=pick_image(data.get("images"), min_size=96) or None,
        complete=complete,
    )


def new_track(data: dict) -> Track:
    return Track(
        id=data["id"],
        name=data["name"],
        duration_ms=data["duration_ms"],
        disc_number=data["disc_number"],
        track_number=data["track_number"],
        artist_ids=[artist["id"] for artist in data["artists"]],
    )
