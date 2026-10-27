import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from .db import SessionLocal
from .models import Playlist, PlaylistCover, utcnow
from .rotation import rotation_lock
from .spotify import RateLimitError, SpotifyError, parse_playlist_id, spotify

log = logging.getLogger(__name__)

MAX_AGE = timedelta(days=1)
MOSAIC_DELAY = timedelta(minutes=2)


def cover_due(playlist: Playlist, now: datetime) -> bool:
    cover = playlist.cover
    if cover is None or cover.checked_at <= now - MAX_AGE:
        return True
    rotated_at = playlist.last_rotated_at
    return rotated_at is not None and cover.checked_at < rotated_at + MOSAIC_DELAY <= now


async def refresh_covers() -> None:
    if rotation_lock.locked():
        return
    with SessionLocal() as session:
        for playlist in session.scalars(select(Playlist)).all():
            spotify_id = playlist.spotify_playlist_id or parse_playlist_id(playlist.spotify_target)
            now = utcnow()
            if not spotify_id or not cover_due(playlist, now):
                continue
            try:
                image = await spotify.playlist_cover(spotify_id)
            except RateLimitError:
                return
            except SpotifyError as error:
                log.warning("Could not load the cover of %s: %s", playlist.name, error)
                image = None if playlist.cover is None else (playlist.cover.content, playlist.cover.content_type)
            content, content_type = image or (b"", "")
            cover = playlist.cover or PlaylistCover(content=b"", content_type="", updated_at=now)
            if (cover.content, cover.content_type) != (content, content_type):
                cover.content, cover.content_type, cover.updated_at = content, content_type, now
            cover.checked_at = now
            playlist.cover = cover
            session.commit()
