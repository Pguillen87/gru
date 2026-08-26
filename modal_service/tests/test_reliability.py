from dataclasses import replace
from datetime import UTC, datetime, timedelta

from modal_service.config import Environment, limits_for
from modal_service.coordinator import JobCoordinator
from modal_service.domain import JobState


def test_expired_worker_becomes_recovery_required_without_retry():
    limits = replace(limits_for(Environment.DEVELOPMENT), worker_lease_seconds=60)
    service = JobCoordinator({}, {}, {}, limits, "2026-08-24")
    job, _ = service.register("uid-a", "key-a", "original/hash", "image-processing-v1")
    service.authorize_generation(job.job_id, "uid-a", enabled=True)
    started, changed = service.start_master_worker(job.job_id)
    assert changed
    service.jobs[job.job_id]["worker_lease_expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()

    recovered = service.recover_stale_workers()

    assert len(recovered) == 1
    assert recovered[0].state is JobState.RECOVERY_REQUIRED
    assert recovered[0].error_code == "WORKER_LOST"
    assert recovered[0].attempts == started.attempts == 1


def test_deletion_removes_private_job_keys_but_keeps_global_limits():
    jobs, idempotency, usage = {}, {}, {}
    service = JobCoordinator(jobs, idempotency, usage, limits_for(Environment.DEVELOPMENT), "2026-08-24")
    job, _ = service.register("uid-a", "key-a", "original/hash", "image-processing-v1")

    deleted = service.delete(job.job_id, "uid-a")

    assert deleted.job_id == job.job_id
    assert job.job_id not in jobs
    assert not idempotency
    assert all("global-jobs" in key for key in usage)
