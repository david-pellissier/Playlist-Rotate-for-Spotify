import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .config import env
from .db import SessionLocal
from .models import Playlist, utcnow
from .rotation import rotate

log = logging.getLogger(__name__)

RETRY_AFTER = timedelta(hours=1)


@dataclass(slots=True)
class Failure:
    retries: int
    retry_at: datetime
    gave_up: bool = False


failures: dict[int, Failure] = {}


def is_due(playlist: Playlist, now: datetime) -> bool:
    failure = failures.get(playlist.id)
    return playlist.next_rotation_at <= now and (failure is None or failure.retry_at <= now)


def record_failure(playlist: Playlist, now: datetime) -> None:
    previous = failures.get(playlist.id)
    retries = previous.retries + 1 if previous and not previous.gave_up else 0
    if retries < env.scheduler_max_retries:
        failures[playlist.id] = Failure(retries, now + RETRY_AFTER)
        log.exception(
            "Scheduled rotation of %s failed, retry %d of %d in %d min",
            playlist.name, retries + 1, env.scheduler_max_retries, RETRY_AFTER.total_seconds() // 60,
        )
    else:
        retry_at = playlist.next_rotation_after(now)
        failures[playlist.id] = Failure(retries, retry_at, gave_up=True)
        local_retry_at = retry_at.replace(tzinfo=UTC).astimezone(env.timezone)
        log.exception(
            "Scheduled rotation of %s failed, giving up until the next scheduled rotation on %s",
            playlist.name, f"{local_retry_at:%Y-%m-%d %H:%M}",
        )


async def rotate_due_playlists() -> None:
    with SessionLocal() as session:
        now = utcnow()
        for playlist in session.scalars(select(Playlist).where(Playlist.enabled)).all():
            if not is_due(playlist, now):
                continue
            try:
                await rotate(session, playlist, dry_run=False)
                failures.pop(playlist.id, None)
            except Exception:
                record_failure(playlist, now)


async def run_scheduler() -> None:
    while True:
        try:
            await rotate_due_playlists()
        except Exception:
            log.exception("Scheduler run failed")
        await asyncio.sleep(env.scheduler_poll_seconds)
