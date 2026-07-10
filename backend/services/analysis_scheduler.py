"""Periodic scheduler for the analysis worker.

Starts a BackgroundScheduler that calls L{process_pending_documents}
at a configurable interval.  The scheduler is safe to start in FastAPI's
lifespan — exceptions from the worker are logged but never propagated.
"""

from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from services.analysis_worker import process_pending_documents

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def get_interval_minutes() -> int:
    """Read ANALYSIS_INTERVAL_MINUTES from the environment (default: 30)."""
    raw = os.getenv("ANALYSIS_INTERVAL_MINUTES", "30")
    try:
        return max(1, int(raw))
    except (ValueError, TypeError):
        return 30


def _run_worker() -> None:
    """Wrapper that catches and logs all worker exceptions."""
    try:
        stats = process_pending_documents()
        logger.info(
            "analysis worker completed: processed=%d events=%d errors=%d",
            stats.get("processed", 0),
            stats.get("events_found", 0),
            stats.get("errors", 0),
        )
    except Exception:
        logger.exception("analysis worker failed")


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler (idempotent)."""
    global _scheduler
    if _scheduler is not None:
        logger.warning("scheduler already running")
        return _scheduler

    interval = get_interval_minutes()
    _scheduler = BackgroundScheduler(
        daemon=True,
        job_defaults={"coalesce": True, "max_instances": 1},
    )
    _scheduler.add_job(
        _run_worker,
        trigger="interval",
        minutes=interval,
        id="analysis_worker",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("analysis scheduler started, interval=%d min", interval)
    return _scheduler


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully (idempotent)."""
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("analysis scheduler stopped")
