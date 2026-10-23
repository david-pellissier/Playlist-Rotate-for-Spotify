import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from .catalog import Entry, load_catalog
from .models import Artist, Playlist, PlaylistTrack, Rotation, RotationTrack, Settings, local_date, utcnow
from .progress import Progress, track
from .spotify import spotify
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


@dataclass(slots=True)
class RotationPlan:
    selections: list[ArtistSelection]
    missing_artists: list[str]
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


def plan_rotation(
    session: Session, playlist: Playlist, artists: list[Artist], missing: list[str], now: datetime
) -> RotationPlan:
    min_cooldown = session.get(Settings, 1).min_cooldown
    catalog = load_catalog(session, playlist, [artist.id for artist in artists])
    cutoff = new_release_cutoff(playlist, now)

    selections = []
    for artist in artists:
        entries = catalog[artist.id]
        eligible = sum(e.eligible for e in entries)
        picks = select_tracks(entries, playlist.songs_per_artist, playlist.max_new_releases, cutoff)
        if len(picks) < playlist.songs_per_artist:
            log.warning("%s: only %d eligible tracks for %s", playlist.name, len(picks), artist.name)
        selections.append(ArtistSelection(
            artist, eligible, artist_cooldown(eligible, playlist.songs_per_artist, min_cooldown), picks
        ))

    order = [pick for selection in selections for pick in selection.picks]
    if playlist.shuffle:
        random.shuffle(order)
    return RotationPlan(selections, missing, order)


def apply_rotation(session: Session, playlist: Playlist, plan: RotationPlan, now: datetime, trigger: str) -> None:
    in_playlist = PlaylistTrack.playlist_id == playlist.id
    session.execute(update(PlaylistTrack).where(in_playlist).values(current=False))
    session.execute(
        update(PlaylistTrack).where(in_playlist, PlaylistTrack.cooldown > 0).values(cooldown=PlaylistTrack.cooldown - 1)
    )

    cooldowns = {selection.artist.id: selection.cooldown for selection in plan.selections}
    for pick in plan.order:
        state = pick.entry.state
        if state is None:
            state = PlaylistTrack(playlist_id=playlist.id, track_id=pick.entry.track.id, disabled=False, play_count=0)
            session.add(state)
        state.current = True
        state.cooldown = cooldowns[pick.entry.album.artist_id]
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


async def _refresh_catalog(
    session: Session, playlist: Playlist, progress: Progress
) -> tuple[list[Artist], list[str]]:
    artists, missing = await resolve_artists(session, playlist.artist_names, progress)
    await sync_artists(session, artists, progress)
    return artists, missing


async def refresh_catalog(session: Session, playlist: Playlist) -> None:
    with track(playlist.id) as progress:
        async with rotation_lock:
            await _refresh_catalog(session, playlist, progress)


async def rotate(session: Session, playlist: Playlist, dry_run: bool, trigger: str = "manual") -> RotationPlan:
    with track(playlist.id) as progress:
        async with rotation_lock:
            return await _rotate(session, playlist, dry_run, trigger, progress)


async def _rotate(
    session: Session, playlist: Playlist, dry_run: bool, trigger: str, progress: Progress
) -> RotationPlan:
    try:
        artists, missing = await _refresh_catalog(session, playlist, progress)
        progress.start("Selecting tracks")
        now = utcnow()
        plan = plan_rotation(session, playlist, artists, missing, now)
        if dry_run:
            return plan
        if not plan.order:
            raise RotationError("No eligible tracks to put in the playlist")
        progress.start("Updating the Spotify playlist")
        if not playlist.spotify_playlist_id:
            playlist.spotify_playlist_id = await spotify.resolve_playlist(playlist.spotify_target)
        await spotify.replace_playlist_items(playlist.spotify_playlist_id, [p.entry.track.uri for p in plan.order])
        apply_rotation(session, playlist, plan, now, trigger)
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
