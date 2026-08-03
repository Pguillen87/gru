"""Serialized, GPU-free coordination for idempotency, ownership and quotas."""

from __future__ import annotations

import hashlib
from collections.abc import MutableMapping
from dataclasses import asdict

from modal_service.config import RuntimeLimits
from modal_service.costs import generation_reservation, require_job_quota
from modal_service.domain import DomainError, JobNotFound, JobRecord, JobState


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

    def register(self, user_id: str, key: str, source_key: str) -> tuple[JobRecord, bool]:
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
        job.generation_reserved = True
        job.transition_to(JobState.VALIDATING_INPUT)
        self.save(job)
        return True
