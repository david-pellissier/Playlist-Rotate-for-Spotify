import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .catalog import Entry, Scope, load_catalog
from .models import (
    Artist, Playlist, PlaylistArtist, PlaylistTrack, Rotation, RotationTrack, Settings, local_date, utcnow,
)
from .progress import Progress, track
from .spotify import spotify
from .links import playlist_scope, sync_links
from .sync import resolve_artists, sync_artists

log = logging.getLogger(__name__)

rotation_lock = asyncio.Lock()


class RotationError(Exception):
    pass


@dataclass(slots=True)
class Pick:
    entry: Entry
    source: str


@dataclass(slots=True)
class ArtistSelection:
    artist: Artist
    eligible: int
    cooldown: int
    picks: list[Pick]
    pool: list[str]


@dataclass(slots=True)
class RotationPlan:
    selections: list[ArtistSelection]
    missing_artists: list[str]
    skipped_artists: list[Artist]
    order: list[Pick]


def new_release_cutoff(playlist: Playlist, now: datetime) -> date:
    return local_date(playlist.last_rotated_at or now - timedelta(days=playlist.update_interval_days))


def artist_cooldown(eligible: int, songs_per_artist: int, min_cooldown: int) -> int:
    return max(min_cooldown, eligible // max(songs_per_artist, 1) - 1)


def select_tracks(entries: list[Entry], count: int, max_new: int, cutoff: date) -> list[Pick]:
    eligible = [e for e in entries if e.eligible]
    available = [e for e in eligible if e.available]

    new = sorted(
        (e for e in available if e.is_new_release(cutoff)),
        key=lambda e: e.released,
        reverse=True,
    )
    picks = [Pick(e, "new") for e in new[:min(max_new, count)]]

    chosen = {p.entry.track.id for p in picks}
    pool = [e for e in available if e.track.id not in chosen]
    random.shuffle(pool)
    pool.sort(key=lambda e: e.play_count)
    picks += [Pick(e, "random") for e in pool[:count - len(picks)]]

    if len(picks) < count:
        fallback = [e for e in eligible if not e.available]
        random.shuffle(fallback)
        fallback.sort(key=lambda e: e.cooldown)
        picks += [Pick(e, "cooldown") for e in fallback[:count - len(picks)]]
    return picks


def has_new_release(entries: list[Entry], cutoff: date) -> bool:
    return any(e.available and e.is_new_release(cutoff) for e in entries)


def choose_artists(
    playlist: Playlist,
    artists: list[Artist],
    catalog: dict[str, list[Entry]],
    last_picked: dict[str, datetime],
    cutoff: date,
) -> list[Artist]:
    if not playlist.max_artists or len(artists) <= playlist.max_artists:
        return artists
    candidates = [artist for artist in artists if any(e.eligible for e in catalog[artist.id])]
    random.shuffle(candidates)
    if playlist.artist_selection == "fair":
        candidates.sort(key=lambda artist: last_picked.get(artist.id, datetime.min))
    if playlist.new_releases_first:
        candidates.sort(key=lambda artist: not has_new_release(catalog[artist.id], cutoff))
    chosen = set(candidates[:playlist.max_artists])
    return [artist for artist in artists if artist in chosen]


def plan_rotation(session: Session, playlist: Playlist, scope: Scope, now: datetime) -> RotationPlan:
    artists = scope.artists
    min_cooldown = session.get(Settings, 1).min_cooldown
    catalog = load_catalog(session, playlist, scope)
    cutoff = new_release_cutoff(playlist, now)
    last_picked = {
        picked.artist_id: picked.last_picked_at
        for picked in session.scalars(select(PlaylistArtist).where(PlaylistArtist.playlist_id == playlist.id))
    }
    chosen = choose_artists(playlist, artists, catalog, last_picked, cutoff)

    selections = []
    for artist in chosen:
        picks = select_tracks(catalog[artist.id], playlist.songs_per_artist, playlist.max_new_releases, cutoff)
        if len(picks) < playlist.songs_per_artist:
            log.warning("%s: only %d eligible tracks for %s", playlist.name, len(picks), artist.name)
        selections.append(artist_selection(playlist, artist, catalog[artist.id], picks, min_cooldown))

    order = [pick for selection in selections for pick in selection.picks]
    if playlist.shuffle:
        random.shuffle(order)
    skipped = [artist for artist in artists if artist not in chosen]
    return RotationPlan(selections, scope.missing, skipped, order)


def replay_plan(session: Session, playlist: Playlist, scope: Scope, planned: list[list[str]]) -> RotationPlan:
    min_cooldown = session.get(Settings, 1).min_cooldown
    catalog = load_catalog(session, playlist, scope)
    entries = {entry.track.id: entry for artist_entries in catalog.values() for entry in artist_entries}
    order = [Pick(entries[track_id], source) for track_id, source in planned if track_id in entries]
    picks: dict[str, list[Pick]] = {}
    for pick in order:
        picks.setdefault(pick.entry.artist_id, []).append(pick)
    selections = [
        artist_selection(playlist, artist, catalog[artist.id], picks[artist.id], min_cooldown)
        for artist in scope.artists if artist.id in picks
    ]
    skipped = [artist for artist in scope.artists if artist.id not in picks]
    return RotationPlan(selections, scope.missing, skipped, order)


def artist_selection(
    playlist: Playlist, artist: Artist, entries: list[Entry], picks: list[Pick], min_cooldown: int
) -> ArtistSelection:
    eligible = sum(e.eligible for e in entries)
    cooldown = artist_cooldown(eligible, playlist.songs_per_artist, min_cooldown)
    return ArtistSelection(artist, eligible, cooldown, picks, [entry.track.id for entry in entries])


def apply_rotation(session: Session, playlist: Playlist, plan: RotationPlan, now: datetime, trigger: str) -> None:
    picked_artists = [selection.artist.id for selection in plan.selections]
    picked_tracks = [track_id for selection in plan.selections for track_id in selection.pool]
    in_playlist = PlaylistTrack.playlist_id == playlist.id
    session.execute(update(PlaylistTrack).where(in_playlist).values(current=False))
    session.execute(
        update(PlaylistTrack)
        .where(in_playlist, PlaylistTrack.cooldown > 0, PlaylistTrack.track_id.in_(picked_tracks))
        .values(cooldown=PlaylistTrack.cooldown - 1)
    )
    for artist_id in picked_artists:
        session.merge(PlaylistArtist(playlist_id=playlist.id, artist_id=artist_id, last_picked_at=now))

    cooldowns = {selection.artist.id: selection.cooldown for selection in plan.selections}
    for pick in plan.order:
        state = pick.entry.state
        if state is None:
            state = PlaylistTrack(playlist_id=playlist.id, track_id=pick.entry.track.id, disabled=False, play_count=0)
            session.add(state)
        state.current = True
        state.cooldown = cooldowns[pick.entry.artist_id]
        state.play_count += 1

    playlist.last_rotated_at = now
    playlist.last_error = None
    session.add(Rotation(
        playlist_id=playlist.id,
        rotated_at=now,
        trigger=trigger,
        tracks=[
            RotationTrack(position=position, track_id=pick.entry.track.id, source=pick.source)
            for position, pick in enumerate(plan.order)
        ],
    ))


async def _refresh_catalog(session: Session, playlist: Playlist, progress: Progress) -> Scope:
    await resolve_artists(session, playlist.artist_names, progress)
    await sync_links(session, playlist, progress)
    scope = playlist_scope(session, playlist)
    await sync_artists(session, [artist for artist in scope.artists if artist.id not in scope.linked], progress)
    return scope


async def refresh_catalog(session: Session, playlist: Playlist) -> None:
    with track(playlist.id) as progress:
        async with rotation_lock:
            await _refresh_catalog(session, playlist, progress)


async def rotate(
    session: Session, playlist: Playlist, dry_run: bool, trigger: str = "manual", planned: list[list[str]] | None = None
) -> RotationPlan:
    with track(playlist.id) as progress:
        async with rotation_lock:
            return await _rotate(session, playlist, dry_run, trigger, progress, planned)


async def rewind(session: Session, playlist: Playlist, rotation: Rotation) -> None:
    if rotation.error or not rotation.tracks:
        raise RotationError("This rotation has no songs to put back")
    with track(playlist.id) as progress:
        async with rotation_lock:
            progress.start("Updating the Spotify playlist")
            if not playlist.spotify_playlist_id:
                playlist.spotify_playlist_id = await spotify.resolve_playlist(playlist.spotify_target)
            uris = [item.track.uri for item in rotation.tracks]
            await spotify.replace_playlist_items(playlist.spotify_playlist_id, uris)
            mark_current(session, playlist, [item.track_id for item in rotation.tracks])
            session.add(Rotation(
                playlist_id=playlist.id,
                rotated_at=utcnow(),
                trigger="rewind",
                tracks=[
                    RotationTrack(position=item.position, track_id=item.track_id, source=item.source)
                    for item in rotation.tracks
                ],
            ))
            session.commit()
            log.info("Rewound %s to the rotation of %s", playlist.name, rotation.rotated_at)


def mark_current(session: Session, playlist: Playlist, track_ids: list[str]) -> None:
    in_playlist = PlaylistTrack.playlist_id == playlist.id
    restored = PlaylistTrack.track_id.in_(track_ids)
    session.execute(update(PlaylistTrack).where(in_playlist).values(current=False))
    session.execute(update(PlaylistTrack).where(in_playlist, restored).values(current=True))
    known = set(session.scalars(select(PlaylistTrack.track_id).where(in_playlist, restored)))
    session.add_all(
        PlaylistTrack(playlist_id=playlist.id, track_id=track_id, current=True)
        for track_id in dict.fromkeys(track_ids) if track_id not in known
    )


async def _rotate(
    session: Session,
    playlist: Playlist,
    dry_run: bool,
    trigger: str,
    progress: Progress,
    planned: list[list[str]] | None,
) -> RotationPlan:
    try:
        scope = playlist_scope(session, playlist) if planned else await _refresh_catalog(session, playlist, progress)
        progress.start("Selecting tracks")
        now = utcnow()
        planned = planned or (None if dry_run else playlist.planned_tracks)
        if planned:
            plan = replay_plan(session, playlist, scope, planned)
        else:
            plan = plan_rotation(session, playlist, scope, now)
        if dry_run:
            return plan
        if not plan.order:
            raise RotationError("No eligible tracks to put in the playlist")
        progress.start("Updating the Spotify playlist")
        if not playlist.spotify_playlist_id:
            playlist.spotify_playlist_id = await spotify.resolve_playlist(playlist.spotify_target)
        await spotify.replace_playlist_items(playlist.spotify_playlist_id, [p.entry.track.uri for p in plan.order])
        apply_rotation(session, playlist, plan, now, trigger)
        playlist.planned_tracks = None
        session.commit()
        log.info("Rotated %s with %d tracks", playlist.name, len(plan.order))
        return plan
    except Exception as error:
        session.rollback()
        if not dry_run:
            playlist.last_error = str(error)
            session.add(Rotation(playlist_id=playlist.id, rotated_at=utcnow(), trigger=trigger, error=str(error)))
            session.commit()
        raise
