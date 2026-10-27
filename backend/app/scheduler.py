import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .config import env
from .covers import refresh_covers
from .db import SessionLocal
from .models import Playlist, utcnow
from .rotation import rotate
from .spotify import RateLimitError

log = logging.getLogger(__name__)

RETRY_AFTER = timedelta(hours=1)


@dataclass(slots=True)
class Failure:
    scheduled_for: datetime
    failed: int
    retry_at: datetime
    gave_up: bool = False


failures: dict[int, Failure] = {}


def current_failure(playlist: Playlist) -> Failure | None:
    failure = failures.get(playlist.id)
    return failure if failure and failure.scheduled_for == playlist.next_rotation_at else None


def is_due(playlist: Playlist, now: datetime) -> bool:
    failure = current_failure(playlist)
    return playlist.next_rotation_at <= now and (failure is None or failure.retry_at <= now)


def failed_so_far(playlist: Playlist) -> int:
    previous = current_failure(playlist)
    return previous.failed if previous and not previous.gave_up else 0


def record_rate_limit(playlist: Playlist, error: RateLimitError) -> None:
    failures[playlist.id] = Failure(playlist.next_rotation_at, failed_so_far(playlist), error.retry_at)
    log.warning("Scheduled rotation of %s postponed: %s", playlist.name, error)


def record_failure(playlist: Playlist, now: datetime) -> None:
    failed = failed_so_far(playlist) + 1
    if failed <= env.scheduler_max_retries:
        failures[playlist.id] = Failure(playlist.next_rotation_at, failed, now + RETRY_AFTER)
        log.exception(
            "Scheduled rotation of %s failed, retry %d of %d in %d min",
            playlist.name, failed, env.scheduler_max_retries, RETRY_AFTER.total_seconds() // 60,
        )
    else:
        retry_at = playlist.next_rotation_after(now)
        failures[playlist.id] = Failure(playlist.next_rotation_at, failed, retry_at, gave_up=True)
        local_retry_at = retry_at.replace(tzinfo=UTC).astimezone(env.timezone)
        log.exception(
            "Scheduled rotation of %s failed, giving up until the next scheduled rotation on %s",
            playlist.name, f"{local_retry_at:%Y-%m-%d %H:%M}",
        )


async def rotate_due_playlists() -> None:
    with SessionLocal() as session:
        for playlist in session.scalars(select(Playlist).where(Playlist.enabled)).all():
            now = utcnow()
            if not is_due(playlist, now):
                continue
            try:
                await rotate(session, playlist, dry_run=False, trigger="scheduled")
                failures.pop(playlist.id, None)
            except RateLimitError as error:
                record_rate_limit(playlist, error)
            except Exception:
                record_failure(playlist, now)


async def run_scheduler() -> None:
    while True:
        try:
            await rotate_due_playlists()
            await refresh_covers()
        except Exception:
            log.exception("Scheduler run failed")
        await asyncio.sleep(env.scheduler_poll_seconds)
