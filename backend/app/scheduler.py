import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .config import env
from .db import SessionLocal
from .models import Playlist, utcnow
from .rotation import rotate

log = logging.getLogger(__name__)


def next_rotation(playlist: Playlist) -> datetime:
    if playlist.last_rotated_at:
        last_rotation = playlist.last_rotated_at.replace(tzinfo=UTC).astimezone(env.timezone)
        day = last_rotation.date() + timedelta(days=playlist.update_interval_days)
    else:
        day = datetime.now(env.timezone).date()
    scheduled = datetime.combine(day, playlist.rotation_time, env.timezone)
    return scheduled.astimezone(UTC).replace(tzinfo=None)


async def rotate_due_playlists() -> None:
    with SessionLocal() as session:
        now = utcnow()
        for playlist in session.scalars(select(Playlist).where(Playlist.enabled)).all():
            if next_rotation(playlist) > now:
                continue
            try:
                await rotate(session, playlist, dry_run=False)
            except Exception:
                log.exception("Scheduled rotation of %s failed", playlist.name)


async def run_scheduler() -> None:
    while True:
        await rotate_due_playlists()
        await asyncio.sleep(env.scheduler_poll_seconds)
