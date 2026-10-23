import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from .config import env
from .db import SessionLocal
from .models import Playlist, utcnow
from .rotation import rotate

log = logging.getLogger(__name__)


def is_due(playlist: Playlist, now: datetime) -> bool:
    return not playlist.last_rotated_at or playlist.last_rotated_at + timedelta(days=playlist.update_interval_days) <= now


async def rotate_due_playlists() -> None:
    with SessionLocal() as session:
        now = utcnow()
        for playlist in session.scalars(select(Playlist).where(Playlist.enabled)).all():
            if not is_due(playlist, now):
                continue
            try:
                await rotate(session, playlist, dry_run=False)
            except Exception:
                log.exception("Scheduled rotation of %s failed", playlist.name)


async def run_scheduler() -> None:
    while True:
        await rotate_due_playlists()
        await asyncio.sleep(env.scheduler_poll_seconds)
