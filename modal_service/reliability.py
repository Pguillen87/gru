"""Lease helpers for detecting workers lost outside Python exception handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from modal_service.domain import JobRecord, JobState


WORKER_LOST = "WORKER_LOST"


def utc_now() -> datetime:
    return datetime.now(UTC)


def start_worker_lease(job: JobRecord, lease_seconds: int, *, now: datetime | None = None) -> None:
    instant = now or utc_now()
    job.worker_started_at = instant.isoformat()
    job.worker_heartbeat_at = instant.isoformat()
    job.worker_lease_expires_at = (instant + timedelta(seconds=lease_seconds)).isoformat()


def renew_worker_lease(job: JobRecord, lease_seconds: int, *, now: datetime | None = None) -> None:
    if job.state is not JobState.GENERATING_MASTER:
        return
    instant = now or utc_now()
    job.worker_heartbeat_at = instant.isoformat()
    job.worker_lease_expires_at = (instant + timedelta(seconds=lease_seconds)).isoformat()


def worker_lease_expired(job: JobRecord, *, now: datetime | None = None) -> bool:
    if job.state is not JobState.GENERATING_MASTER or not job.worker_lease_expires_at:
        return False
    try:
        expires = datetime.fromisoformat(job.worker_lease_expires_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    return expires <= (now or utc_now())
