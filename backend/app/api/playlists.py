import math
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..catalog import Entry, album_automatic_exclusion, load_catalog
from ..db import get_session
from ..models import Album, DisabledAlbum, EnabledAlbum, EnabledTrack, Playlist, PlaylistTrack, Rule, Track, utcnow
from ..progress import running_jobs
from ..rotation import Pick, new_release_cutoff, refresh_catalog, rotate
from ..schemas import (
    AlbumOut, ArtistOut, CatalogOut, PickOut, PlaylistIn, PlaylistOut, PlaylistSummary, ProgressOut,
    EnabledIn, RotationOut, RuleIn, RuleOut, SelectionOut, TrackOut,
)
from ..sync import known_artists

router = APIRouter(prefix="/api/playlists")

ARTISTS_PER_PAGE = 20
STATUS_FILTERS = {
    "all": lambda e, cutoff: True,
    "eligible": lambda e, cutoff: e.eligible,
    "new": lambda e, cutoff: e.is_new_release(cutoff),
    "excluded": lambda e, cutoff: not e.eligible,
    "cooldown": lambda e, cutoff: e.cooldown > 0,
    "current": lambda e, cutoff: e.current,
}


def get_playlist(playlist_id: int, session: Session = Depends(get_session)) -> Playlist:
    playlist = session.get(Playlist, playlist_id)
    if playlist is None:
        raise HTTPException(404, "Playlist not found")
    return playlist


def commit_or_conflict(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "A playlist with this name already exists")


@router.get("", response_model=list[PlaylistSummary])
def list_playlists(session: Session = Depends(get_session)):
    return [
        PlaylistSummary(
            id=p.id,
            name=p.name,
            spotify_target=p.spotify_target,
            artist_count=len(p.artist_names),
            enabled=p.enabled,
            update_interval_days=p.update_interval_days,
            rotation_time=p.rotation_time,
            last_rotated_at=p.last_rotated_at,
            next_rotation_at=p.next_rotation_at,
            last_error=p.last_error,
        )
        for p in session.scalars(select(Playlist).order_by(Playlist.name))
    ]


@router.post("", response_model=PlaylistOut, status_code=201)
def create_playlist(data: PlaylistIn, session: Session = Depends(get_session)):
    playlist = Playlist(**data.model_dump())
    session.add(playlist)
    commit_or_conflict(session)
    return playlist


@router.get("/{playlist_id}", response_model=PlaylistOut)
def read_playlist(playlist: Playlist = Depends(get_playlist)):
    return playlist


@router.put("/{playlist_id}", response_model=PlaylistOut)
def update_playlist(data: PlaylistIn, playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)):
    if data.spotify_target != playlist.spotify_target:
        playlist.spotify_playlist_id = None
    for field, value in data.model_dump().items():
        setattr(playlist, field, value)
    commit_or_conflict(session)
    return playlist


@router.delete("/{playlist_id}", status_code=204)
def delete_playlist(playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)):
    session.delete(playlist)
    session.commit()


@router.post("/{playlist_id}/rules", response_model=RuleOut, status_code=201)
def create_playlist_rule(data: RuleIn, playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)):
    rule = Rule(playlist_id=playlist.id, **data.model_dump())
    session.add(rule)
    session.commit()
    return rule


@router.get("/{playlist_id}/catalog", response_model=CatalogOut)
def read_catalog(
    artist_id: str | None = None,
    q: str = "",
    status: Literal["all", "eligible", "new", "excluded", "cooldown", "current"] = "all",
    page: int = Query(1, ge=1),
    playlist: Playlist = Depends(get_playlist),
    session: Session = Depends(get_session),
):
    artists, missing = known_artists(session, playlist.artist_names)
    catalog = load_catalog(session, playlist, [artist.id for artist in artists])
    names = {artist.id: artist.name for artist in artists}
    matches = STATUS_FILTERS[status]
    cutoff = new_release_cutoff(playlist, utcnow())
    query = q.strip().casefold()

    selected = {
        current_artist: [e for e in catalog.get(current_artist, []) if matches(e, cutoff) and matches_query(e, query)]
        for current_artist in ([artist_id] if artist_id else names)
    }
    matching_artists = [current_artist for current_artist, entries in selected.items() if entries]
    page = min(page, max(1, math.ceil(len(matching_artists) / ARTISTS_PER_PAGE)))
    start = (page - 1) * ARTISTS_PER_PAGE
    page_entries = [
        entry for current_artist in matching_artists[start:start + ARTISTS_PER_PAGE] for entry in selected[current_artist]
    ]

    albums: dict[str, AlbumOut] = {}
    for entry in page_entries:
        album = albums.get(entry.album.id) or albums.setdefault(entry.album.id, AlbumOut(
            id=entry.album.id,
            artist_name=names[entry.album.artist_id],
            name=entry.album.name,
            album_type=entry.album.album_type,
            release_date=entry.album.release_date,
            image_url=entry.album.image_url,
            exclusion=entry.album_status.exclusion,
            excluded_by=entry.album_status.excluded_by,
            forced=entry.album_status.forced,
            tracks=[],
        ))
        album.tracks.append(track_out(entry, cutoff))

    return CatalogOut(
        artists=[
            ArtistOut(
                id=artist.id,
                name=artist.name,
                image_url=artist.image_url or None,
                total=len(catalog[artist.id]),
                eligible=sum(e.eligible for e in catalog[artist.id]),
                on_cooldown=sum(e.cooldown > 0 for e in catalog[artist.id]),
            )
            for artist in artists
        ],
        missing_artists=missing,
        albums=list(albums.values()),
        total_tracks=sum(len(entries) for entries in selected.values()),
        total_artists=len(matching_artists),
        page=page,
        page_size=ARTISTS_PER_PAGE,
    )


@router.put("/{playlist_id}/albums/{album_id}", status_code=204)
def set_album_enabled(
    album_id: str, data: EnabledIn, playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)
):
    album = session.get(Album, album_id)
    if album is None:
        raise HTTPException(404, "Album not found")
    key = (playlist.id, album_id)
    delete_if_present(session, DisabledAlbum, key)
    delete_if_present(session, EnabledAlbum, key)
    excluded_by_rule = album_automatic_exclusion(session, playlist, album) is not None
    if data.enabled and excluded_by_rule:
        session.add(EnabledAlbum(playlist_id=playlist.id, album_id=album_id))
    elif not data.enabled and not excluded_by_rule:
        session.add(DisabledAlbum(playlist_id=playlist.id, album_id=album_id))
    session.commit()


@router.put("/{playlist_id}/tracks/{track_id}", status_code=204)
def set_track_enabled(
    track_id: str, data: EnabledIn, playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)
):
    track = session.get(Track, track_id)
    if track is None:
        raise HTTPException(404, "Track not found")
    artist_id = track.album.artist_id
    entry = next(e for e in load_catalog(session, playlist, [artist_id])[artist_id] if e.track.id == track_id)
    excluded_automatically = entry.status.automatic is not None

    state = session.get(PlaylistTrack, (playlist.id, track_id))
    if state is None:
        state = PlaylistTrack(playlist_id=playlist.id, track_id=track_id, cooldown=0, current=False, play_count=0)
        session.add(state)
    state.disabled = not data.enabled and not excluded_automatically

    delete_if_present(session, EnabledTrack, (playlist.id, track_id))
    if data.enabled and excluded_automatically:
        session.add(EnabledTrack(playlist_id=playlist.id, track_id=track_id))
    session.commit()


def delete_if_present(session: Session, model: type, key: tuple) -> None:
    if row := session.get(model, key):
        session.delete(row)
        session.flush()


@router.post("/{playlist_id}/clear-cooldowns", status_code=204)
def clear_cooldowns(playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)):
    session.execute(update(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist.id).values(cooldown=0))
    session.commit()


@router.post("/{playlist_id}/sync", status_code=204)
async def sync_playlist(playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)):
    await refresh_catalog(session, playlist)


@router.get("/{playlist_id}/progress", response_model=ProgressOut | None)
def read_progress(playlist_id: int):
    return running_jobs.get(playlist_id)


@router.post("/{playlist_id}/rotate", response_model=RotationOut)
async def rotate_playlist(
    dry_run: bool = True,
    playlist: Playlist = Depends(get_playlist),
    session: Session = Depends(get_session),
):
    plan = await rotate(session, playlist, dry_run)
    return RotationOut(
        dry_run=dry_run,
        selections=[
            SelectionOut(
                artist_name=selection.artist.name,
                eligible=selection.eligible,
                cooldown=selection.cooldown,
                picks=[pick_out(pick) for pick in selection.picks],
            )
            for selection in plan.selections
        ],
        missing_artists=plan.missing_artists,
        skipped_artists=[artist.name for artist in plan.skipped_artists],
        order=[pick_out(pick) for pick in plan.order],
    )


def matches_query(entry: Entry, query: str) -> bool:
    return not query or query in entry.track.name.casefold() or query in entry.album.name.casefold()


def track_out(entry: Entry, cutoff: date) -> TrackOut:
    return TrackOut(
        id=entry.track.id,
        name=entry.track.name,
        duration=entry.track.duration_ms // 1000,
        released=entry.released,
        exclusion=entry.exclusion,
        new_release=entry.is_new_release(cutoff),
        excluded_by=entry.status.excluded_by,
        forced=entry.status.forced,
        cooldown=entry.cooldown,
        current=entry.current,
        play_count=entry.play_count,
    )


def pick_out(pick: Pick) -> PickOut:
    track, album = pick.entry.track, pick.entry.album
    return PickOut(
        track_id=track.id,
        name=track.name,
        album_name=album.name,
        artist_name=album.artist.name,
        duration=track.duration_ms // 1000,
        source=pick.source,
    )
