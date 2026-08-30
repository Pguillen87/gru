"""Serialized, GPU-free coordination for idempotency, ownership and quotas."""

from __future__ import annotations

import hashlib
from collections.abc import MutableMapping
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from modal_service.config import RuntimeLimits
from modal_service.costs import generation_reservation, require_job_quota
from modal_service.domain import DomainError, JobNotFound, JobRecord, JobState, TERMINAL_STATES, WorkflowMode, utc_now
from modal_service.catalog import DEFAULT_POSE_CHOICES, validate_pose_choices


class JobOperation(StrEnum):
    AUTHORIZE_GENERATION = "AUTHORIZE_GENERATION"
    START_MASTER = "START_MASTER"
    COMMIT_MASTER = "COMMIT_MASTER"
    RECONCILE_MASTER = "RECONCILE_MASTER"
    FAIL_MASTER = "FAIL_MASTER"
    RECORD_GPU_CALL = "RECORD_GPU_CALL"
    RESERVE_POSE_GPU_CALL = "RESERVE_POSE_GPU_CALL"
    RECORD_POSE_GPU_CALL = "RECORD_POSE_GPU_CALL"
    APPROVE_MASTER = "APPROVE_MASTER"
    UPDATE_CONFIGURATION = "UPDATE_CONFIGURATION"
    START_POSES = "START_POSES"
    COMMIT_POSES = "COMMIT_POSES"
    FAIL_POSES = "FAIL_POSES"
    ENQUEUE_POSES = "ENQUEUE_POSES"
    CANCEL = "CANCEL"
    DELETE = "DELETE"
    AUTO_SELECT_MASTER = "AUTO_SELECT_MASTER"
    RECORD_SHADOW_RANKING = "RECORD_SHADOW_RANKING"
    FAIL_INCUBATION = "FAIL_INCUBATION"
    CLAIM_INCUBATION_LEASE = "CLAIM_INCUBATION_LEASE"
    HEARTBEAT_INCUBATION = "HEARTBEAT_INCUBATION"
    RELEASE_INCUBATION_LEASE = "RELEASE_INCUBATION_LEASE"


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
        workflow_mode: str = WorkflowMode.LEGACY_MANUAL.value,
        subject_hint: dict[str, object] | None = None,
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
            if existing.workflow_mode != workflow_mode:
                raise DomainError("Idempotency key was already used with a different workflow mode.")
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
            if existing.workflow_mode != workflow_mode:
                raise DomainError("Idempotency key was already used with a different workflow mode.")
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
            workflow_mode=workflow_mode,
            subject_hint=subject_hint,
            subject_hint_policy_version=str(subject_hint.get("version")) if subject_hint else None,
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
        self._reserve_generation_budget(user_id)
        job.generation_reserved = True
        job.transition_to(JobState.VALIDATING_INPUT)
        self.save(job)
        return True

    def _reserve_generation_budget(self, user_id: str) -> None:
        """Reserve one GPU operation before a worker can be queued.

        Master and pose work share the same user and staging budget: either
        operation consumes a real GPU window and must be blocked before state
        transition when a cap is exhausted.
        """
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
        if job.state in TERMINAL_STATES or job.gpu_call_id is not None:
            return job, False
        job.gpu_call_id = call_id
        self.save(job)
        return job, True

    def reserve_pose_gpu_call(self, job_id: str) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state is not JobState.GENERATING_POSES or job.pose_gpu_call_id is not None:
            return job, False
        job.pose_gpu_call_id = "reserved"
        self.save(job)
        return job, True

    def record_pose_gpu_call(self, job_id: str, call_id: str) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state is not JobState.GENERATING_POSES or job.pose_gpu_call_id != "reserved":
            return job, False
        job.pose_gpu_call_id = call_id
        job.pose_operation_status = "running"
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

    def auto_select_master(self, job_id: str, selection: dict[str, object], prompt_version: str) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.workflow_mode != WorkflowMode.ASYNC_INCUBATOR_V1.value:
            raise DomainError("Automatic Master selection is not available for this workflow.")
        selected = str(selection.get("selectedMasterId", ""))
        if not selected:
            raise DomainError("Automatic Master selection is incomplete.")
        if job.master_selection:
            if job.master_selection != selection or job.master_id != selected:
                raise DomainError("A different Master selection is already recorded.")
            return job, False
        changed = job.approve_master(selected)
        job.master_selection = selection
        job.encoder_version = str(selection.get("encoderVersion") or "") or None
        job.master_ranker_version = str(selection.get("masterRankerVersion") or "") or None
        job.prompt_version = prompt_version
        self.save(job)
        return job, changed

    def record_shadow_ranking(self, job_id: str, observation: dict[str, object]) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state is not JobState.AWAITING_MASTER_APPROVAL or job.master_selection:
            raise DomainError("Shadow ranking is not available for this job.")
        if job.shadow_ranking_observation:
            if job.shadow_ranking_observation != observation:
                raise DomainError("A different shadow ranking is already recorded.")
            return job, False
        job.shadow_ranking_observation = observation
        job.encoder_version = str(observation.get("encoderVersion") or "") or None
        job.master_ranker_version = str(observation.get("masterRankerVersion") or "") or None
        self.save(job)
        return job, True

    def update_configuration(
        self,
        job_id: str,
        user_id: str,
        display_name: str | None,
        pose_choices: dict[str, str] | None,
        expected_revision: int,
    ) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        self.ensure_owner(job, user_id)
        if job.state not in {JobState.CONSISTENCY_TEST, JobState.READY_FOR_POSES}:
            raise DomainError("Mascot configuration is not available for this job.")
        next_choices = validate_pose_choices(pose_choices) if pose_choices is not None else job.pose_choices
        next_name = display_name if display_name is not None else job.display_name
        if expected_revision != job.configuration_revision:
            # A transport retry may arrive after the first write. It is safe
            # only when it describes the state already persisted; divergent
            # stale edits remain a visible conflict.
            if next_choices == job.pose_choices and next_name == job.display_name:
                return job, False
            error = DomainError("Mascot configuration was changed in another session.")
            error.code = "POSE_CONFIGURATION_CONFLICT"
            raise error
        changed = next_choices != job.pose_choices or next_name != job.display_name
        if changed:
            job.pose_choices = next_choices
            job.display_name = next_name
            job.configuration_revision += 1
            job.updated_at = utc_now()
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

    def enqueue_pose_generation(
        self,
        job_id: str,
        user_id: str,
        pose_choices: dict[str, str],
        operation_id: str,
        operation_fingerprint: str,
        correlation_id: str | None,
        request_id: str | None,
    ) -> tuple[JobRecord, bool, bool]:
        job = self.get(job_id)
        self.ensure_owner(job, user_id)
        selected_poses = validate_pose_choices(pose_choices)
        if job.pose_operation_id:
            if job.pose_operation_fingerprint != operation_fingerprint or job.pose_choices != selected_poses:
                raise DomainError("Pose choices cannot change after the operation is reserved.")
            return job, False, False
        if not job.master_id:
            raise DomainError("An approved Master is required for pose generation.")

        self._reserve_generation_budget(user_id)

        job.pose_choices = selected_poses
        job.pose_operation_id = operation_id
        job.pose_operation_fingerprint = operation_fingerprint
        job.pose_operation_status = "queued"
        job.pose_request_id = request_id
        if correlation_id:
            job.correlation_id = correlation_id
        job.start_pose_generation()
        job.pose_operation_created_at = job.updated_at
        job.pose_gpu_call_id = "reserved"
        job.pose_generation_reserved = True
        self.save(job)
        return job, True, True

    def fail_pose_generation(self, job_id: str, error_code: str) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state is not JobState.GENERATING_POSES:
            return job, False
        job.transition_to(JobState.FAILED)
        job.error_code = error_code
        job.pose_operation_status = "failed"
        self.save(job)
        return job, True

    def fail_incubation(self, job_id: str, error_code: str) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state in TERMINAL_STATES:
            return job, False
        if job.workflow_mode != WorkflowMode.ASYNC_INCUBATOR_V1.value:
            raise DomainError("Incubation failure is not available for this workflow.")
        job.error_code = error_code
        job.transition_to(JobState.FAILED)
        self.save(job)
        return job, True

    def claim_incubation_lease(self, job_id: str, owner: str, ttl_seconds: int = 90) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.workflow_mode != WorkflowMode.ASYNC_INCUBATOR_V1.value or job.state in TERMINAL_STATES:
            return job, False
        now = datetime.now(UTC)
        expires_at = datetime.fromisoformat(job.lease_expires_at) if job.lease_expires_at else None
        if job.lease_owner and job.lease_owner != owner and expires_at and expires_at > now:
            return job, False
        job.lease_owner = owner
        job.lease_expires_at = (now + timedelta(seconds=max(15, min(ttl_seconds, 300)))).isoformat()
        job.heartbeat_at = now.isoformat()
        job.workflow_revision += 1
        self.save(job)
        return job, True

    def heartbeat_incubation(self, job_id: str, owner: str, ttl_seconds: int = 90) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.lease_owner != owner or job.state in TERMINAL_STATES:
            return job, False
        now = datetime.now(UTC)
        job.heartbeat_at = now.isoformat()
        job.lease_expires_at = (now + timedelta(seconds=max(15, min(ttl_seconds, 300)))).isoformat()
        self.save(job)
        return job, True

    def release_incubation_lease(self, job_id: str, owner: str) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.lease_owner != owner:
            return job, False
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = utc_now()
        self.save(job)
        return job, True

    def commit_pose_outputs(self, job_id: str, persist: Callable[[JobRecord], None]) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        if job.state in TERMINAL_STATES or job.state is not JobState.GENERATING_POSES:
            return job, False
        persist(job)
        changed = job.complete_pose_generation(job.job_id)
        job.pose_operation_status = "completed"
        if job.workflow_mode == WorkflowMode.ASYNC_INCUBATOR_V1.value:
            job.generation_ready_at = utc_now()
        self.save(job)
        return job, changed

    def cancel(self, job_id: str, user_id: str) -> tuple[JobRecord, bool]:
        job = self.get(job_id)
        self.ensure_owner(job, user_id)
        changed = job.cancel()
        if changed:
            self.save(job)
        return job, changed

    def delete(self, job_id: str, user_id: str) -> JobRecord:
        job = self.get(job_id)
        self.ensure_owner(job, user_id)
        del self.jobs[job_id]
        for key in list(self.idempotency.keys()):
            if self.idempotency.get(key) == job_id:
                del self.idempotency[key]
        return job
