from collections.abc import Awaitable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(slots=True)
class Progress:
    step: str = "Waiting for another job to finish"
    done: int = 0
    total: int = 0

    def start(self, step: str, total: int = 0) -> None:
        self.step = step
        self.done = 0
        self.total = total

    async def count[T](self, awaitable: Awaitable[T]) -> T:
        result = await awaitable
        self.done += 1
        return result


running_jobs: dict[int, Progress] = {}


@contextmanager
def track(playlist_id: int) -> Iterator[Progress]:
    progress = running_jobs[playlist_id] = Progress()
    try:
        yield progress
    finally:
        if running_jobs.get(playlist_id) is progress:
            del running_jobs[playlist_id]
