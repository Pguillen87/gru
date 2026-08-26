"""Serialized, GPU-free coordination for idempotency, ownership and quotas."""

from __future__ import annotations

import hashlib
from collections.abc import MutableMapping
from collections.abc import Callable
from dataclasses import asdict
from enum import StrEnum

from modal_service.config import RuntimeLimits
from modal_service.costs import generation_reservation, require_job_quota
from modal_service.domain import DomainError, JobNotFound, JobRecord, JobState, TERMINAL_STATES
from modal_service.reliability import WORKER_LOST, renew_worker_lease, start_worker_lease, worker_lease_expired


RECOVERABLE_MASTER_ERRORS = frozenset({WORKER_LOST, "MASTER_GENERATION_FAILED"})


class JobOperation(StrEnum):
    AUTHORIZE_GENERATION = "AUTHORIZE_GENERATION"
    START_MASTER = "START_MASTER"
    COMMIT_MASTER = "COMMIT_MASTER"
    FAIL_MASTER = "FAIL_MASTER"
    RECORD_GPU_CALL = "RECORD_GPU_CALL"
    APPROVE_MASTER = "APPROVE_MASTER"
    VALIDATE_MASTER = "VALIDATE_MASTER"
    START_POSES = "START_POSES"
    COMMIT_POSES = "COMMIT_POSES"
    FAIL_POSES = "FAIL_POSES"
    CANCEL = "CANCEL"
    HEARTBEAT_WORKER = "HEARTBEAT_WORKER"
    RESUME_MASTER = "RESUME_MASTER"
    DELETE = "DELETE"


def deterministic_job_id(user_id: str, idempotency_key: str) -> str:
    digest = hashlib.sha256(f"{user_id}\0{idempotency_key}".encode()).hexdigest()[:32]
    return f"job_{digest}"


def owner_counter_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:32]


class JobCoordinator:
    def __init__(
        self,
        job_store: MutableMapping[str, object],
        idempotency_store: MutableMapping[str, object],
        usage_store: MutableMapping[str, object],
        limits: RuntimeLimits,
        day_key: str,
    ) -> None:
        self.jobs = job_store
        self.idempotency = idempotency_store
        self.usage = usage_store
        self.limits = limits
        self.day_key = day_key

    def get(self, job_id: str) -> JobRecord:
        try:
            value = dict(self.jobs[job_id])
        except KeyError as error:
            raise JobNotFound("Job was not found.") from error
        return JobRecord(**(value | {"state": JobState(value["state"])}))

    def save(self, job: JobRecord) -> None:
        self.jobs[job.job_id] = asdict(job) | {"state": job.state.value}

    @staticmethod
    def ensure_owner(job: JobRecord, user_id: str) -> None:
        if job.user_id != user_id:
            raise JobNotFound("Job was not found.")

    def register(
        self,
        user_id: str,
        key: str,
        source_key: str,
        consent_policy_version: str,
        subject_identity: dict[str, object] | None = None,
    ) -> tuple[JobRecord, bool]:
        request_key = f"create:{user_id}:{key}"
        existing_id = self.idempotency.get(request_key)
        if existing_id:
            existing = self.get(str(existing_id))
            if existing.source_key != source_key:
                raise DomainError("Idempotency key was already used with different input.")
            return existing, False

        job_id = deterministic_job_id(user_id, key)
        try:
            existing = self.get(job_id)
            if existing.source_key != source_key:
                raise DomainError("Idempotency key was already used with different input.")
            self.idempotency[request_key] = existing.job_id
            return existing, False
        except JobNotFound:
            pass

        quota_key = f"user-jobs:{self.day_key}:{owner_counter_id(user_id)}"
        global_quota_key = f"global-jobs:{self.day_key}"
        next_user_jobs = require_job_quota(int(self.usage.get(quota_key, 0)), self.limits.jobs_per_user_per_day)
        next_global_jobs = require_job_quota(int(self.usage.get(global_quota_key, 0)), self.limits.global_jobs_per_day)
        self.usage[quota_key] = next_user_jobs
        self.usage[global_quota_key] = next_global_jobs
        job = JobRecord(
            job_id=job_id,
            user_id=user_id,
            idempotency_key=key,
            source_key=source_key,
            model_version="Qwen-Image-Edit-2511",
            consent_policy_version=consent_policy_version,
            subject_identity=dict(subject_identity or {}),
        )
        job.transition_to(JobState.VALIDATING_INPUT)
        job.transition_to(JobState.READY_FOR_GENERATION)
        self.save(job)
        self.idempotency[request_key] = job.job_id
        return job, True

    def authorize_generation(self, job_id: str, user_id: str, enabled: bool) -> bool:
        if not enabled:
            return False
        job = self.get(job_id)
        self.ensure_owner(job, user_id)
        if job.state is not JobState.READY_FOR_GENERATION or job.generation_reserved:
            return False
        owner_id = owner_counter_id(user_id)
        generation_key = f"user-generations:{self.day_key}:{owner_id}"
        next_user_generations = require_job_quota(
            int(self.usage.get(generation_key, 0)), self.limits.generations_per_user_per_day
        )
        global_key = f"global-cost:{self.day_key}"
        user_key = f"user-cost:{self.day_key}:{owner_id}"
        next_global, next_user = generation_reservation(
            float(self.usage.get(global_key, 0.0)),
            float(self.usage.get(user_key, 0.0)),
            self.limits.estimated_generation_cost_usd,
            self.limits.daily_cost_cap_usd,
            self.limits.user_daily_cost_cap_usd,
        )
        self.usage[global_key] = next_global
        self.usage[user_key] = next_user
        self.usage[generation_key] = next_user_generations
        job.generation_reserved = True
        job.transition_to(JobState.VALIDATING_INPUT)
        self.save(job)
        return True

    def start_master_worker(self, job_id: str) -> tuple[JobRecord, bool]:
        job, changed = self.transition_if_active(job_id, JobState.VALIDATING_INPUT, JobState.GENERATING_MASTER)
        if changed:
            start_worker_lease(job, self.limits.worker_lease_seconds)
            job.attempts += 1
            self.save(job)
        return job, changed

    def resume_preempted_master(self, job_id: str, user_id: str) -> tuple[JobRecord, bool]:
        """Resume a known recoverable Master failure without another reservation."""
        job = self.get(job_id)
        self.ensure_owner(job, user_id)
        if job.error_code not in RECOVERABLE_MASTER_ERRORS or not job.generation_reserved:
            return job, False
        if job.state is JobState.FAILED:
            job.transition_to(JobState.RECOVERY_REQUIRED)
        if job.state is not JobState.RECOVERY_REQUIRED:
            return job, False
        job.error_code = None
        job.gpu_call_id = None
        job.worker_started_at = None
        job.worker_heartbeat_at = None
        job.worker_lease_expires_at = None
        job.transition_to(JobState.VALIDATING_INPUT)
        self.save(job)
        return job, True

    def heartbeat_worker(self, job_id: str) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state is not JobState.GENERATING_MASTER:
            return job, False
        renew_worker_lease(job, self.limits.worker_lease_seconds)
        self.save(job)
        return job, True

    def recover_stale_workers(self) -> list[JobRecord]:
        recovered: list[JobRecord] = []
        for job_id in list(self.jobs.keys()):
            job = self.get(str(job_id))
            if worker_lease_expired(job):
                job.error_code = WORKER_LOST
                job.transition_to(JobState.RECOVERY_REQUIRED)
                self.save(job)
                recovered.append(job)
        return recovered

    def delete(self, job_id: str, user_id: str) -> JobRecord:
        job = self.get(job_id)
        self.ensure_owner(job, user_id)
        del self.jobs[job_id]
        for key in list(self.idempotency.keys()):
            if self.idempotency.get(key) == job_id:
                del self.idempotency[key]
        owner_id = owner_counter_id(user_id)
        for key in list(self.usage.keys()):
            if str(key).endswith(f":{owner_id}"):
                del self.usage[key]
        return job

    def transition_if_active(
        self,
        job_id: str,
        expected: JobState,
        target: JobState,
        error_code: str | None = None,
    ) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state in TERMINAL_STATES or job.state is not expected:
            return job, False
        job.error_code = error_code
        job.transition_to(target)
        self.save(job)
        return job, True

    def commit_master_outputs(
        self,
        job_id: str,
        persist: Callable[[JobRecord], None],
    ) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state in TERMINAL_STATES or job.state is not JobState.GENERATING_MASTER:
            return job, False
        job.transition_to(JobState.VALIDATING_MASTERS)
        persist(job)
        job.transition_to(JobState.AWAITING_MASTER_APPROVAL)
        self.save(job)
        return job, True

    def record_gpu_call(self, job_id: str, call_id: str) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state in TERMINAL_STATES:
            return job, False
        job.gpu_call_id = call_id
        self.save(job)
        return job, True

    def approve_master(self, job_id: str, user_id: str, master_id: str, prompt_version: str) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        self.ensure_owner(job, user_id)
        if job.state in TERMINAL_STATES:
            return job, False
        changed = job.approve_master(master_id)
        if changed:
            job.prompt_version = prompt_version
            self.save(job)
        return job, changed

    def validate_master(self, job_id: str) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state is not JobState.VALIDATING_MASTER:
            return job, False
        job.mark_master_valid()
        self.save(job)
        return job, True

    def start_pose_worker(
        self,
        job_id: str,
        user_id: str,
        pose_choices: dict[str, str],
        catalog_version: str,
        operation_id: str,
    ) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        self.ensure_owner(job, user_id)
        if job.state is not JobState.READY_FOR_POSES:
            return job, False
        job.pose_choices = dict(pose_choices)
        job.catalog_version = catalog_version
        job.active_operation_id = operation_id
        job.transition_to(JobState.GENERATING_POSES)
        self.save(job)
        return job, True

    def commit_pose_outputs(self, job_id: str, persist: Callable[[JobRecord], None]) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state is not JobState.GENERATING_POSES:
            return job, False
        job.transition_to(JobState.VALIDATING_POSES)
        persist(job)
        job.transition_to(JobState.AWAITING_SET_APPROVAL)
        self.save(job)
        return job, True

    def cancel(self, job_id: str, user_id: str) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        self.ensure_owner(job, user_id)
        changed = job.cancel()
        if changed:
            self.save(job)
        return job, changed
