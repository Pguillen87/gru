"""Stable, framework-independent GRU Mascot domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Mapping
from uuid import uuid4

from modal_service.catalog import MASTER_PROMPT_VERSION, POSE_TEMPLATE_VERSION

class JobState(StrEnum):
    QUEUED = "QUEUED"
    VALIDATING_INPUT = "VALIDATING_INPUT"
    READY_FOR_GENERATION = "READY_FOR_GENERATION"
    GENERATING_MASTER = "GENERATING_MASTER"
    VALIDATING_MASTERS = "VALIDATING_MASTERS"
    AWAITING_MASTER_APPROVAL = "AWAITING_MASTER_APPROVAL"
    VALIDATING_MASTER = "VALIDATING_MASTER"
    CONSISTENCY_TEST = "CONSISTENCY_TEST"  # V1 compatibility alias/state
    CONSISTENCY_FAILED = "CONSISTENCY_FAILED"
    READY_FOR_POSES = "READY_FOR_POSES"
    GENERATING_POSES = "GENERATING_POSES"
    VALIDATING_POSES = "VALIDATING_POSES"
    AWAITING_SET_APPROVAL = "AWAITING_SET_APPROVAL"
    PACKAGING = "PACKAGING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    CANCELED = "CANCELED"


TERMINAL_STATES = frozenset({JobState.COMPLETED, JobState.FAILED, JobState.CANCELED})

ALLOWED_TRANSITIONS: Mapping[JobState, frozenset[JobState]] = {
    JobState.QUEUED: frozenset({JobState.VALIDATING_INPUT, JobState.CANCELED}),
    JobState.VALIDATING_INPUT: frozenset({JobState.READY_FOR_GENERATION, JobState.GENERATING_MASTER, JobState.FAILED, JobState.CANCELED}),
    JobState.READY_FOR_GENERATION: frozenset({JobState.VALIDATING_INPUT, JobState.CANCELED}),
    JobState.GENERATING_MASTER: frozenset({JobState.VALIDATING_MASTERS, JobState.AWAITING_MASTER_APPROVAL, JobState.FAILED, JobState.RECOVERY_REQUIRED, JobState.CANCELED}),
    JobState.VALIDATING_MASTERS: frozenset({JobState.AWAITING_MASTER_APPROVAL, JobState.FAILED, JobState.CANCELED}),
    JobState.AWAITING_MASTER_APPROVAL: frozenset({JobState.VALIDATING_MASTER, JobState.CONSISTENCY_TEST, JobState.CANCELED}),
    JobState.VALIDATING_MASTER: frozenset({JobState.READY_FOR_POSES, JobState.AWAITING_MASTER_APPROVAL, JobState.FAILED, JobState.CANCELED}),
    JobState.CONSISTENCY_TEST: frozenset({JobState.READY_FOR_POSES, JobState.CONSISTENCY_FAILED, JobState.FAILED, JobState.CANCELED}),
    JobState.CONSISTENCY_FAILED: frozenset({JobState.GENERATING_MASTER, JobState.CANCELED}),
    JobState.READY_FOR_POSES: frozenset({JobState.GENERATING_POSES, JobState.CANCELED}),
    JobState.GENERATING_POSES: frozenset({JobState.VALIDATING_POSES, JobState.FAILED, JobState.RECOVERY_REQUIRED, JobState.CANCELED}),
    JobState.VALIDATING_POSES: frozenset({JobState.AWAITING_SET_APPROVAL, JobState.FAILED, JobState.CANCELED}),
    JobState.AWAITING_SET_APPROVAL: frozenset({JobState.PACKAGING, JobState.CANCELED}),
    JobState.PACKAGING: frozenset({JobState.COMPLETED, JobState.FAILED, JobState.CANCELED}),
    JobState.COMPLETED: frozenset(),
    # A narrowly classified worker failure may be resumed with its original
    # reservation after the underlying service issue has been corrected.
    JobState.FAILED: frozenset({JobState.RECOVERY_REQUIRED}),
    # A preempted worker retains the same reservation and may resume.
    JobState.RECOVERY_REQUIRED: frozenset({JobState.VALIDATING_INPUT, JobState.CANCELED}),
    JobState.CANCELED: frozenset(),
}


class DomainError(ValueError):
    """A safe error which may be shown to the integration client."""


class JobNotFound(DomainError):
    code = "JOB_NOT_FOUND"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def require_transition(current: JobState, target: JobState) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise DomainError(f"Cannot transition from {current} to {target}.")


@dataclass(frozen=True)
class BenchmarkScore:
    identity: float
    pose: float
    style: float
    anatomy: float
    cost_speed: float
    operations_license: float

    def total(self) -> float:
        return round(
            self.identity * 0.40
            + self.pose * 0.20
            + self.style * 0.15
            + self.anatomy * 0.10
            + self.cost_speed * 0.10
            + self.operations_license * 0.05,
            2,
        )

    def passes(self, total_gate: float = 8.2, identity_gate: float = 9.0, critical_gate: float = 8.0) -> bool:
        return self.total() >= total_gate and self.identity >= identity_gate and min(
            self.identity, self.pose, self.style, self.anatomy
        ) >= critical_gate


@dataclass
class JobRecord:
    job_id: str
    user_id: str
    idempotency_key: str
    source_key: str
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    state: JobState = JobState.QUEUED
    master_id: str | None = None
    pose_set_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    model_version: str = "qwen-image-edit-2511"
    prompt_version: str = MASTER_PROMPT_VERSION
    template_version: str = POSE_TEMPLATE_VERSION
    attempts: int = 0
    error_code: str | None = None
    generation_reserved: bool = False
    gpu_call_id: str | None = None
    worker_started_at: str | None = None
    worker_heartbeat_at: str | None = None
    worker_lease_expires_at: str | None = None
    consent_policy_version: str | None = None
    subject_identity: dict[str, object] = field(default_factory=dict)
    pose_choices: dict[str, str] = field(default_factory=dict)
    catalog_version: str | None = None
    active_operation_id: str | None = None

    def transition_to(self, target: JobState) -> None:
        require_transition(self.state, target)
        self.state = target
        self.updated_at = utc_now()

    def approve_master(self, master_id: str) -> bool:
        if self.master_id == master_id:
            return False
        if self.master_id is not None:
            raise DomainError("A different master is already approved for this job.")
        if self.state is not JobState.AWAITING_MASTER_APPROVAL:
            raise DomainError("Master approval is not available for this job.")
        self.master_id = master_id
        # Web v2 persists a confirmed identity and receives the stricter QC
        # transition. Legacy Android v1 keeps its existing consistency state.
        self.transition_to(JobState.VALIDATING_MASTER if self.subject_identity else JobState.CONSISTENCY_TEST)
        return True

    def mark_master_valid(self) -> None:
        if self.state is not JobState.VALIDATING_MASTER or self.master_id is None:
            raise DomainError("The approved Master is not ready for validation.")
        self.transition_to(JobState.READY_FOR_POSES)

    def cancel(self) -> bool:
        if self.state is JobState.CANCELED:
            return False
        if self.state in TERMINAL_STATES:
            return False
        self.transition_to(JobState.CANCELED)
        return True
