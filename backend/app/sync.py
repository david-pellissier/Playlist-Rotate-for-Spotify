import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import batched

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import SPOTIFY_LINK, Album, Artist, Playlist, Settings, Track, utcnow
from .progress import Progress
from .spotify import RateLimitError, SpotifyError, gather_all, parse_release_date, pick_image, spotify

log = logging.getLogger(__name__)

RESYNC_AFTER = timedelta(hours=1)
ALBUM_BATCH = 20


@dataclass(slots=True)
class Scope:
    artists: list[Artist]
    missing: list[str]
    linked: dict[str, set[str]]


def playlist_scope(session: Session, playlist: Playlist) -> Scope:
    by_name = {artist.name.casefold(): artist for artist in session.scalars(select(Artist))}
    artist_ids = [item_id for _, kind, item_id in playlist.links if kind == "artist"]
    album_ids = [item_id for _, kind, item_id in playlist.links if kind == "album"]
    track_ids = [item_id for _, kind, item_id in playlist.links if kind == "track"]
    by_id = {artist.id: artist for artist in session.scalars(select(Artist).where(Artist.id.in_(artist_ids)))}
    albums = {
        album.id: album
        for album in session.scalars(
            select(Album).where(Album.id.in_(album_ids), Album.complete).options(selectinload(Album.tracks))
        )
    }
    tracks = {track.id: track for track in session.scalars(select(Track).where(Track.id.in_(track_ids)))}

    artists: dict[str, Artist] = {}
    named: set[str] = set()
    linked: dict[str, set[str]] = {}
    missing: list[str] = []
    for entry in playlist.entries:
        match = SPOTIFY_LINK.search(entry)
        kind, item_id = match.groups() if match else ("name", entry)
        if kind in ("name", "artist"):
            artist = by_name.get(entry.casefold()) if kind == "name" else by_id.get(item_id)
            if artist is None:
                missing.append(entry)
                continue
            artists.setdefault(artist.id, artist)
            named.add(artist.id)
            continue
        found = albums.get(item_id) if kind == "album" else tracks.get(item_id)
        if found is None:
            missing.append(entry)
            continue
        album = found if kind == "album" else found.album
        artists.setdefault(album.artist_id, album.artist)
        linked.setdefault(album.artist_id, set()).update(t.id for t in (album.tracks if kind == "album" else [found]))
    return Scope(list(artists.values()), missing, {a: ids for a, ids in linked.items() if a not in named})


async def resolve_artists(session: Session, names: list[str], progress: Progress) -> None:
    known = {name.casefold() for name in session.scalars(select(Artist.name))}
    unknown = [name for name in names if name.casefold() not in known]
    progress.start("Finding artists", len(unknown))
    found = await gather_all(progress.count(spotify.find_artist(name)) for name in unknown)

    for name, data in zip(unknown, found):
        if data is None:
            log.error("No exact Spotify match for artist %r", name)
        elif artist := session.get(Artist, data["id"]):
            artist.name = data["name"]
            artist.image_url = pick_image(data.get("images"))
        else:
            session.add(Artist(id=data["id"], name=data["name"], image_url=pick_image(data.get("images"))))
    session.commit()


async def sync_links(session: Session, playlist: Playlist, progress: Progress) -> None:
    links = [(kind, item_id) for _, kind, item_id in playlist.links]
    known = {
        "artist": set(session.scalars(select(Artist.id).where(Artist.id.in_([i for k, i in links if k == "artist"])))),
        "album": set(session.scalars(
            select(Album.id).where(Album.id.in_([i for k, i in links if k == "album"]), Album.complete)
        )),
        "track": set(session.scalars(select(Track.id).where(Track.id.in_([i for k, i in links if k == "track"])))),
    }
    wanted = [(kind, item_id) for kind, item_id in links if item_id not in known[kind]]
    if not wanted:
        return

    progress.start("Loading linked artists, albums and songs", len(wanted))
    loaders = {"artist": _load_artist, "album": _load_album, "track": _load_track}
    artists: set[Artist] = set()
    for kind, item_id in wanted:
        try:
            artists.add(await loaders[kind](session, item_id))
            session.commit()
        except RateLimitError:
            raise
        except SpotifyError as error:
            session.rollback()
            log.warning("Could not load the Spotify %s %s: %s", kind, item_id, error)
        progress.done += 1
    for artist in artists:
        if artist.image_url is None:
            await _load_image(artist)
            session.commit()


async def _load_artist(session: Session, artist_id: str) -> Artist:
    data = await spotify.artist(artist_id)
    artist = _stored_artist(session, data)
    artist.image_url = pick_image(data.get("images"))
    return artist


async def _load_album(session: Session, album_id: str) -> Artist:
    data = await spotify.album(album_id)
    tracks = await spotify.album_tracks(album_id)
    artist = _stored_artist(session, data["artists"][0])
    _store_album(session, artist, data, tracks)
    return artist


async def _load_track(session: Session, track_id: str) -> Artist:
    data = await spotify.track(track_id)
    artist = _stored_artist(session, data["album"]["artists"][0])
    album = session.get(Album, data["album"]["id"])
    if album is None:
        album = _album(artist, data["album"], complete=False)
        session.add(album)
    album.tracks.append(_track(data))
    return artist


def _stored_artist(session: Session, data: dict) -> Artist:
    artist = session.get(Artist, data["id"])
    if artist is None:
        artist = Artist(id=data["id"], name=data["name"])
        session.add(artist)
    return artist


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
            await _load_image(artist)
            session.commit()
        new_albums = await _sync_artist(session, artist, lookback, singles[artist.id])
        artist.synced_at = utcnow()
        artist.singles_synced = singles[artist.id]
        session.commit()
        progress.done += 1
        if new_albums:
            log.info("Synced %s: %d new albums", artist.name, new_albums)


async def _load_image(artist: Artist) -> None:
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
            _store_album(session, artist, data, tracks)
        session.commit()
    return len(new_albums)


def _store_album(session: Session, artist: Artist, data: dict, tracks: list[dict]) -> None:
    track_ids = [track["id"] for track in tracks if track.get("id")]
    stored = set(session.scalars(select(Track.id).where(Track.id.in_(track_ids))))
    new_tracks = [_track(track) for track in {t["id"]: t for t in tracks if t.get("id") and t["id"] not in stored}.values()]
    album = session.get(Album, data["id"])
    if album is None:
        album = _album(artist, data)
        session.add(album)
    album.tracks.extend(new_tracks)
    album.complete = True


def _album(artist: Artist, data: dict, complete: bool = True) -> Album:
    return Album(
        id=data["id"],
        artist_id=artist.id,
        name=data["name"],
        album_type=data["album_type"],
        release_date=parse_release_date(data["release_date"]),
        image_url=pick_image(data.get("images"), min_size=96) or None,
        complete=complete,
    )


def _track(data: dict) -> Track:
    return Track(
        id=data["id"],
        name=data["name"],
        duration_ms=data["duration_ms"],
        disc_number=data["disc_number"],
        track_number=data["track_number"],
        artist_ids=[artist["id"] for artist in data["artists"]],
    )
