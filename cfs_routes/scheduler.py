"""
APScheduler 3.x integration for automatic AIRAC cycle ingestion.
"""
from __future__ import annotations

import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from cfs_routes.airac import current_cfs_cycle, next_cfs_cycle
from cfs_routes.config import settings
from cfs_routes.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _check_and_ingest() -> None:
    from cfs_routes import ingest

    today = date.today()
    async with AsyncSessionLocal() as db:
        cur = current_cfs_cycle(today)
        logger.info("Scheduler: checking current cycle %s", cur.ident)
        await ingest.ensure_cycle(db, cur)

        nxt = next_cfs_cycle(today)
        days_until_next = (nxt.effective - today).days
        if days_until_next <= settings.fetch_retry_days_before:
            logger.info(
                "Scheduler: next cycle %s is in %d days, pre-fetching",
                nxt.ident,
                days_until_next,
            )
            await ingest.ensure_cycle(db, nxt)


async def _startup_check() -> None:
    logger.info("Startup: checking current cycle ingestion")
    await _check_and_ingest()


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def start_scheduler() -> None:
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled by config")
        return

    sched = get_scheduler()

    sched.add_job(
        _check_and_ingest,
        CronTrigger(hour="*/3", minute=0, timezone="UTC"),
        id="cycle_check",
        replace_existing=True,
    )

    sched.start()
    logger.info("Scheduler started")

    await _startup_check()


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
