"""A guard for the CPU-heavy endpoints: the model explanations (SHAP, LIME, LRP, DiCE) and the
learner reports. One API process has few cores, so a burst of these could slow every other
request. Each user gets at most XAI_REQUESTS_PER_MINUTE of them, at most XAI_MAX_CONCURRENT run
at once, and a few more may queue briefly; anything beyond that gets a 503 with Retry-After.

Owner: Mit.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from fastapi import HTTPException, status

from app.auth.limits import windows
from app.config import settings

MAX_WAITING = 8  # requests queued for a slot; each holds a server thread while it waits


class _Slots:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._size = 0
        self._semaphore = threading.BoundedSemaphore(1)
        self.waiting = 0

    def semaphore(self) -> threading.BoundedSemaphore:
        with self._lock:
            if self._size != settings.xai_max_concurrent:  # settings changed (tests)
                self._size = max(1, settings.xai_max_concurrent)
                self._semaphore = threading.BoundedSemaphore(self._size)
            return self._semaphore

    def queue(self) -> bool:
        with self._lock:
            if self.waiting >= MAX_WAITING:
                return False
            self.waiting += 1
            return True

    def dequeue(self) -> None:
        with self._lock:
            self.waiting -= 1


_slots = _Slots()


def _busy() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": {
                "code": "SERVER_BUSY",
                "message": "The server is busy working out other explanations. Try again shortly.",
            }
        },
        headers={"Retry-After": "5"},
    )


@contextmanager
def heavy_work(user_id: UUID) -> Iterator[None]:
    """Run the body under the per-user limit and the concurrency cap."""
    if settings.rate_limit_enabled and (
        wait := windows.hit(f"xai:{user_id}", settings.xai_requests_per_minute, 60)
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "TOO_MANY_EXPLANATION_REQUESTS",
                    "message": "Too many explanation requests. Try again in a minute.",
                }
            },
            headers={"Retry-After": str(wait)},
        )
    semaphore = _slots.semaphore()
    if not semaphore.acquire(blocking=False):
        if not _slots.queue():
            raise _busy()
        try:
            acquired = semaphore.acquire(timeout=settings.xai_wait_seconds)
        finally:
            _slots.dequeue()
        if not acquired:
            raise _busy()
    try:
        yield
    finally:
        semaphore.release()
