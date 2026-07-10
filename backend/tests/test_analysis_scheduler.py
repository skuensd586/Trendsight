"""Tests for the analysis scheduler module."""

from __future__ import annotations

from unittest.mock import patch

from services.analysis_scheduler import (
    _run_worker,
    get_interval_minutes,
    start_scheduler,
    stop_scheduler,
)


class TestGetIntervalMinutes:
    def test_default(self):
        """No env var set returns 30."""
        val = get_interval_minutes()
        assert val == 30

    def test_custom(self, monkeypatch):
        monkeypatch.setenv("ANALYSIS_INTERVAL_MINUTES", "15")
        assert get_interval_minutes() == 15

    def test_min_clamp(self, monkeypatch):
        monkeypatch.setenv("ANALYSIS_INTERVAL_MINUTES", "0")
        assert get_interval_minutes() == 1

    def test_negative(self, monkeypatch):
        monkeypatch.setenv("ANALYSIS_INTERVAL_MINUTES", "-5")
        assert get_interval_minutes() == 1

    def test_invalid(self, monkeypatch):
        monkeypatch.setenv("ANALYSIS_INTERVAL_MINUTES", "abc")
        assert get_interval_minutes() == 30


class TestSchedulerLifecycle:
    def test_start_stop(self):
        """Scheduler starts, registers job, stops cleanly."""
        sched = start_scheduler()
        assert sched.running
        assert sched.get_job("analysis_worker") is not None
        stop_scheduler()
        # second stop is a no-op
        stop_scheduler()

    def test_idempotent_start(self):
        """Calling start_scheduler twice returns the same instance."""
        first = start_scheduler()
        second = start_scheduler()
        assert first is second
        stop_scheduler()

    def test_job_calls_worker(self):
        """The registered job function delegates to process_pending_documents."""
        with patch(
            "services.analysis_scheduler.process_pending_documents"
        ) as mock:
            mock.return_value = {
                "processed": 5, "events_found": 2, "errors": 0,
            }
            sched = start_scheduler()
            job = sched.get_job("analysis_worker")
            assert job is not None
            # Call the underlying function synchronously
            job.func()
            mock.assert_called_once()
            stop_scheduler()
