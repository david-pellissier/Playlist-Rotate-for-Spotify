from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..catalog import Entry, load_catalog
from ..db import get_session
from ..models import Album, DisabledAlbum, Playlist, PlaylistTrack, Rule, Track
from ..rotation import Pick, refresh_catalog, rotate, rotation_lock
from ..schemas import (
    AlbumOut, ArtistOut, CatalogOut, PickOut, PlaylistIn, PlaylistOut, PlaylistSummary,
    RotationOut, RuleIn, RuleOut, SelectionOut, ToggleIn, TrackOut,
)
from ..sync import known_artists

router = APIRouter(prefix="/api/playlists")

CATALOG_PAGE_SIZE = 250
STATUS_FILTERS = {
    "all": lambda e: True,
    "eligible": lambda e: e.eligible,
    "excluded": lambda e: not e.eligible,
    "cooldown": lambda e: e.cooldown > 0,
    "current": lambda e: e.current,
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
            last_rotated_at=p.last_rotated_at,
            next_rotation_at=p.last_rotated_at + timedelta(days=p.update_interval_days) if p.last_rotated_at else None,
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
    status: Literal["all", "eligible", "excluded", "cooldown", "current"] = "all",
    page: int = Query(1, ge=1),
    playlist: Playlist = Depends(get_playlist),
    session: Session = Depends(get_session),
):
    artists, missing = known_artists(session, playlist.artist_names)
    catalog = load_catalog(session, playlist, [artist.id for artist in artists])
    disabled_albums = set(session.scalars(
        select(DisabledAlbum.album_id).where(DisabledAlbum.playlist_id == playlist.id)
    ))
    names = {artist.id: artist.name for artist in artists}
    matches = STATUS_FILTERS[status]
    query = q.strip().casefold()

    selected = [
        entry
        for current_artist in ([artist_id] if artist_id else names)
        for entry in catalog.get(current_artist, [])
        if matches(entry) and matches_query(entry, query)
    ]
    start = (page - 1) * CATALOG_PAGE_SIZE

    albums: dict[str, AlbumOut] = {}
    for entry in selected[start:start + CATALOG_PAGE_SIZE]:
        album = albums.get(entry.album.id) or albums.setdefault(entry.album.id, AlbumOut(
            id=entry.album.id,
            artist_name=names[entry.album.artist_id],
            name=entry.album.name,
            album_type=entry.album.album_type,
            release_date=entry.album.release_date,
            image_url=entry.album.image_url,
            disabled=entry.album.id in disabled_albums,
            tracks=[],
        ))
        album.tracks.append(track_out(entry))

    return CatalogOut(
        artists=[
            ArtistOut(
                id=artist.id,
                name=artist.name,
                total=len(catalog[artist.id]),
                eligible=sum(e.eligible for e in catalog[artist.id]),
                on_cooldown=sum(e.cooldown > 0 for e in catalog[artist.id]),
            )
            for artist in artists
        ],
        missing_artists=missing,
        albums=list(albums.values()),
        total_tracks=len(selected),
        page=page,
        page_size=CATALOG_PAGE_SIZE,
    )


@router.put("/{playlist_id}/albums/{album_id}", status_code=204)
def toggle_album(album_id: str, data: ToggleIn, playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)):
    if session.get(Album, album_id) is None:
        raise HTTPException(404, "Album not found")
    disabled = session.get(DisabledAlbum, (playlist.id, album_id))
    if data.disabled and disabled is None:
        session.add(DisabledAlbum(playlist_id=playlist.id, album_id=album_id))
    elif not data.disabled and disabled is not None:
        session.delete(disabled)
    session.commit()


@router.put("/{playlist_id}/tracks/{track_id}", status_code=204)
def toggle_track(track_id: str, data: ToggleIn, playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)):
    if session.get(Track, track_id) is None:
        raise HTTPException(404, "Track not found")
    state = session.get(PlaylistTrack, (playlist.id, track_id))
    if state is None:
        state = PlaylistTrack(playlist_id=playlist.id, track_id=track_id, cooldown=0, current=False, play_count=0)
        session.add(state)
    state.disabled = data.disabled
    session.commit()


@router.post("/{playlist_id}/clear-cooldowns", status_code=204)
def clear_cooldowns(playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)):
    session.execute(update(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist.id).values(cooldown=0))
    session.commit()


@router.post("/{playlist_id}/sync", status_code=204)
async def sync_playlist(playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)):
    async with rotation_lock:
        await refresh_catalog(session, playlist)


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
        order=[pick_out(pick) for pick in plan.order],
    )


def matches_query(entry: Entry, query: str) -> bool:
    return not query or query in entry.track.name.casefold() or query in entry.album.name.casefold()


def track_out(entry: Entry) -> TrackOut:
    return TrackOut(
        id=entry.track.id,
        name=entry.track.name,
        duration=entry.track.duration_ms // 1000,
        released=entry.released,
        exclusion=entry.exclusion,
        disabled=bool(entry.state and entry.state.disabled),
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
