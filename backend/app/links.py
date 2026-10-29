import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .catalog import Scope, song_artist_id
from .models import SPOTIFY_LINK, Album, Artist, Playlist, Track, utcnow
from .progress import Progress
from .spotify import NotFoundError, RateLimitError, SpotifyError, pick_image, spotify
from .sync import failed_lookups, load_image, new_album, new_track, recently_failed, store_album, stored_artist

log = logging.getLogger(__name__)


def playlist_scope(session: Session, playlist: Playlist) -> Scope:
    links = playlist.links
    all_artists = session.scalars(select(Artist)).all()
    by_name = {artist.name.casefold(): artist for artist in all_artists}
    by_id = {artist.id: artist for artist in all_artists}
    albums = {
        album.id: album
        for album in session.scalars(
            select(Album)
            .where(Album.id.in_([i for _, kind, i in links if kind == "album"]), Album.complete)
            .options(selectinload(Album.tracks))
        )
    }
    tracks = {
        track.id: track
        for track in session.scalars(select(Track).where(Track.id.in_([i for _, kind, i in links if kind == "track"])))
    }

    scope = Scope([])
    artists: dict[str, Artist] = {}
    named: set[str] = set()
    for entry in playlist.entries:
        match = SPOTIFY_LINK.search(entry)
        kind, item_id = match.groups() if match else ("name", entry)
        if kind in ("name", "artist"):
            artist = by_name.get(entry.casefold()) if kind == "name" else by_id.get(item_id)
            if artist is None:
                scope.missing.append(entry)
                continue
            artists.setdefault(artist.id, artist)
            named.add(artist.id)
            continue
        found = albums.get(item_id) if kind == "album" else tracks.get(item_id)
        if found is None:
            scope.missing.append(entry)
            continue
        album = found if kind == "album" else found.album
        for track in album.tracks if kind == "album" else [found]:
            owner = song_artist_id(track, album)
            if owner in by_id:
                artists.setdefault(owner, by_id[owner])
                scope.linked.setdefault(owner, set()).add(track.id)
                scope.linked_tracks.add(track.id)
    scope.artists = list(artists.values())
    scope.linked = {artist_id: ids for artist_id, ids in scope.linked.items() if artist_id not in named}
    return scope


async def sync_links(session: Session, playlist: Playlist, progress: Progress) -> None:
    links = [(kind, item_id) for _, kind, item_id in playlist.links]
    ids = {kind: [i for k, i in links if k == kind] for kind in ("artist", "album", "track")}
    known = {
        "artist": set(session.scalars(select(Artist.id).where(Artist.id.in_(ids["artist"])))),
        "album": set(session.scalars(select(Album.id).where(Album.id.in_(ids["album"]), Album.complete))),
        "track": set(session.scalars(select(Track.id).where(Track.id.in_(ids["track"])))),
    }
    wanted = list(dict.fromkeys((kind, i) for kind, i in links if i not in known[kind] and not recently_failed(i)))
    if not wanted:
        return

    progress.start("Loading linked artists, albums and songs", len(wanted))
    loaders = {"artist": _load_artist, "album": _load_album, "track": _load_track}
    artists: set[Artist] = set()
    for kind, item_id in wanted:
        try:
            artists.update(await loaders[kind](session, item_id))
            session.commit()
        except RateLimitError:
            raise
        except SpotifyError as error:
            session.rollback()
            if isinstance(error, NotFoundError):
                failed_lookups[item_id] = utcnow()
            log.warning("Could not load the Spotify %s %s: %s", kind, item_id, error)
        progress.done += 1
    for artist in artists:
        if artist.image_url is None:
            await load_image(artist)
            session.commit()


async def _load_artist(session: Session, artist_id: str) -> list[Artist]:
    data = await spotify.artist(artist_id)
    artist = stored_artist(session, data)
    artist.image_url = pick_image(data.get("images"))
    return [artist]


async def _load_album(session: Session, album_id: str) -> list[Artist]:
    data = await spotify.album(album_id)
    tracks = await spotify.album_tracks(album_id)
    artist = stored_artist(session, data["artists"][0])
    store_album(session, artist, data, tracks)
    if data["album_type"] != "compilation":
        return [artist]
    return [stored_artist(session, track["artists"][0]) for track in tracks if track.get("artists")]


async def _load_track(session: Session, track_id: str) -> list[Artist]:
    if session.get(Track, track_id):
        return []
    data = await spotify.track(track_id)
    artist = stored_artist(session, data["album"]["artists"][0])
    album = session.get(Album, data["album"]["id"])
    if album is None:
        album = new_album(artist, data["album"], complete=False)
        session.add(album)
    album.tracks.append(new_track(data))
    return [stored_artist(session, data["artists"][0])] if data["album"]["album_type"] == "compilation" else [artist]
