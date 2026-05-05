from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import select

from .config import settings
from .database import create_session
from .models import Monitor, utc_now
from .services import run_monitor_check


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class MonitorScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_CHECKS)
        self._domain_locks: dict[str, asyncio.Lock] = {}
        self._running_ids: set[int] = set()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(self._loop())

    def configure(self, *, max_concurrent_checks: int) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent_checks)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            await self._queue_due_monitors()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                pass

    async def _queue_due_monitors(self) -> None:
        now = utc_now()
        with create_session() as db:
            monitors = db.scalars(select(Monitor).where(Monitor.enabled.is_(True))).all()
            due_ids = []
            for monitor in monitors:
                if monitor.id in self._running_ids:
                    continue
                if monitor.last_checked_at is None:
                    due_ids.append(monitor.id)
                    continue
                jitter = random.randint(-monitor.jitter_seconds, monitor.jitter_seconds) if monitor.jitter_seconds else 0
                backoff_multiplier = 4 if monitor.failure_count >= 5 else 2 if monitor.failure_count >= 3 else 1
                due_after = timedelta(seconds=max(10, monitor.interval_seconds * backoff_multiplier + jitter))
                if _as_utc(monitor.last_checked_at) + due_after <= now:
                    due_ids.append(monitor.id)

        for monitor_id in due_ids:
            self._running_ids.add(monitor_id)
            asyncio.create_task(self._run_one(monitor_id))

    async def _run_one(self, monitor_id: int) -> None:
        async with self._semaphore:
            with create_session() as db:
                monitor = db.get(Monitor, monitor_id)
                domain = urlparse(monitor.url).netloc if monitor else ""
            domain_lock = self._domain_locks.setdefault(domain, asyncio.Lock())
            async with domain_lock:
                try:
                    with create_session() as db:
                        await run_monitor_check(db, monitor_id)
                finally:
                    self._running_ids.discard(monitor_id)


scheduler = MonitorScheduler()
