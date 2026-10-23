import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..models import Album, Playlist, Rotation, RotationTrack, Track
from ..schemas import HistoryOut, RotationSummary, RotationTrackOut
from .playlists import get_playlist

router = APIRouter(prefix="/api/playlists")

HISTORY_PAGE_SIZE = 20


@router.get("/{playlist_id}/history", response_model=HistoryOut)
def read_history(
    page: int = Query(1, ge=1),
    playlist: Playlist = Depends(get_playlist),
    session: Session = Depends(get_session),
):
    total = session.scalar(select(func.count()).select_from(Rotation).where(Rotation.playlist_id == playlist.id))
    page = min(page, max(1, math.ceil(total / HISTORY_PAGE_SIZE)))
    rows = session.execute(
        select(
            Rotation,
            func.count(RotationTrack.position),
            func.count(RotationTrack.position).filter(RotationTrack.source == "new"),
        )
        .outerjoin(RotationTrack)
        .where(Rotation.playlist_id == playlist.id)
        .group_by(Rotation.id)
        .order_by(Rotation.rotated_at.desc())
        .offset((page - 1) * HISTORY_PAGE_SIZE)
        .limit(HISTORY_PAGE_SIZE)
    )
    return HistoryOut(
        rotations=[
            RotationSummary(
                id=rotation.id,
                rotated_at=rotation.rotated_at,
                trigger=rotation.trigger,
                error=rotation.error,
                track_count=track_count,
                new_releases=new_releases,
            )
            for rotation, track_count, new_releases in rows
        ],
        total=total,
        page=page,
        page_size=HISTORY_PAGE_SIZE,
    )


@router.delete("/{playlist_id}/history", status_code=204)
def clear_history(playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)):
    session.execute(delete(Rotation).where(Rotation.playlist_id == playlist.id))
    session.commit()


@router.get("/{playlist_id}/history/{rotation_id}", response_model=list[RotationTrackOut])
def read_rotation(
    rotation_id: int, playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)
):
    tracks = selectinload(Rotation.tracks).selectinload(RotationTrack.track)
    rotation = session.scalar(
        select(Rotation)
        .where(Rotation.id == rotation_id, Rotation.playlist_id == playlist.id)
        .options(tracks.selectinload(Track.album).selectinload(Album.artist))
    )
    if rotation is None:
        raise HTTPException(404, "Rotation not found")
    return [
        RotationTrackOut(
            position=item.position,
            track_id=item.track_id,
            name=item.track.name,
            artist_name=item.track.album.artist.name,
            album_name=item.track.album.name,
            duration=item.track.duration_ms // 1000,
            source=item.source,
        )
        for item in rotation.tracks
    ]
