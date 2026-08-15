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
from modal_service.catalog import DEFAULT_POSE_CHOICES, validate_pose_choices


class JobOperation(StrEnum):
    AUTHORIZE_GENERATION = "AUTHORIZE_GENERATION"
    START_MASTER = "START_MASTER"
    COMMIT_MASTER = "COMMIT_MASTER"
    RECONCILE_MASTER = "RECONCILE_MASTER"
    FAIL_MASTER = "FAIL_MASTER"
    RECORD_GPU_CALL = "RECORD_GPU_CALL"
    APPROVE_MASTER = "APPROVE_MASTER"
    START_POSES = "START_POSES"
    COMMIT_POSES = "COMMIT_POSES"
    FAIL_POSES = "FAIL_POSES"
    CANCEL = "CANCEL"


def deterministic_job_id(user_id: str, idempotency_key: str) -> str:
    digest = hashlib.sha256(f"{user_id}\0{idempotency_key}".encode()).hexdigest()[:32]
    return f"job_{digest}"


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
        pose_choices: dict[str, str] | None = None,
        subject_identity: dict[str, object] | None = None,
        *,
        registration_only: bool = False,
        attempt_id: str | None = None,
        correlation_id: str | None = None,
    ) -> tuple[JobRecord, bool]:
        selected_poses = validate_pose_choices(pose_choices or dict(DEFAULT_POSE_CHOICES))
        confirmed_identity = subject_identity or {
            "category": "other",
            "label": "confirmed subject",
            "species": None,
        }
        request_key = f"create:{user_id}:{key}"
        existing_id = self.idempotency.get(request_key)
        if existing_id:
            existing = self.get(str(existing_id))
            if existing.source_key != source_key:
                raise DomainError("Idempotency key was already used with different input.")
            if existing.pose_choices != selected_poses:
                raise DomainError("Idempotency key was already used with different pose choices.")
            if existing.subject_identity != confirmed_identity:
                raise DomainError("Idempotency key was already used with a different subject identity.")
            if existing.attempt_id != attempt_id:
                raise DomainError("Idempotency key was already used with a different attempt.")
            return existing, False

        job_id = deterministic_job_id(user_id, key)
        try:
            existing = self.get(job_id)
            if existing.source_key != source_key:
                raise DomainError("Idempotency key was already used with different input.")
            if existing.pose_choices != selected_poses:
                raise DomainError("Idempotency key was already used with different pose choices.")
            if existing.subject_identity != confirmed_identity:
                raise DomainError("Idempotency key was already used with a different subject identity.")
            if existing.attempt_id != attempt_id:
                raise DomainError("Idempotency key was already used with a different attempt.")
            self.idempotency[request_key] = existing.job_id
            return existing, False
        except JobNotFound:
            pass

        quota_key = f"user-jobs:{self.day_key}:{user_id}"
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
            pose_choices=selected_poses,
            subject_identity=confirmed_identity,
            attempt_id=attempt_id,
            correlation_id=correlation_id,
        )
        if registration_only:
            job.state = JobState.REGISTERED
            job.updated_at = job.created_at
        else:
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
        if job.state not in {JobState.REGISTERED, JobState.READY_FOR_GENERATION} or job.generation_reserved:
            return False
        generation_key = f"user-generations:{self.day_key}:{user_id}"
        next_user_generations = require_job_quota(
            int(self.usage.get(generation_key, 0)), self.limits.generations_per_user_per_day
        )
        global_key = f"global-cost:{self.day_key}"
        user_key = f"user-cost:{self.day_key}:{user_id}"
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
        persist(job)
        job.transition_to(JobState.AWAITING_MASTER_APPROVAL)
        self.save(job)
        return job, True

    def fail_stale_master(self, job_id: str, error_code: str) -> tuple[JobRecord, bool]:
        """Fail only a still-running Master job; terminal/newer states win."""
        return self.transition_if_active(job_id, JobState.GENERATING_MASTER, JobState.FAILED, error_code)

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

    def start_pose_generation(self, job_id: str, pose_choices: dict[str, str]) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state in TERMINAL_STATES:
            return job, False
        selected_poses = validate_pose_choices(pose_choices)
        if job.state is JobState.GENERATING_POSES:
            if job.pose_choices != selected_poses:
                raise DomainError("Pose generation is already active with different choices.")
            return job, False
        job.pose_choices = selected_poses
        changed = job.start_pose_generation()
        if changed:
            self.save(job)
        return job, changed

    def commit_pose_outputs(self, job_id: str, persist: Callable[[JobRecord], None]) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state in TERMINAL_STATES or job.state is not JobState.GENERATING_POSES:
            return job, False
        persist(job)
        changed = job.complete_pose_generation(job.job_id)
        self.save(job)
        return job, changed

    def cancel(self, job_id: str, user_id: str) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        self.ensure_owner(job, user_id)
        changed = job.cancel()
        if changed:
            self.save(job)
        return job, changed
