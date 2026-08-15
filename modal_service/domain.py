"""Stable, framework-independent GRU Mascot domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Mapping

from modal_service.catalog import DEFAULT_POSE_CHOICES, MASTER_PROMPT_VERSION, POSE_TEMPLATE_VERSION


class JobState(StrEnum):
    REGISTERED = "REGISTERED"
    QUEUED = "QUEUED"
    VALIDATING_INPUT = "VALIDATING_INPUT"
    READY_FOR_GENERATION = "READY_FOR_GENERATION"
    GENERATING_MASTER = "GENERATING_MASTER"
    AWAITING_MASTER_APPROVAL = "AWAITING_MASTER_APPROVAL"
    CONSISTENCY_TEST = "CONSISTENCY_TEST"
    CONSISTENCY_FAILED = "CONSISTENCY_FAILED"
    READY_FOR_POSES = "READY_FOR_POSES"
    GENERATING_POSES = "GENERATING_POSES"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


TERMINAL_STATES = frozenset({JobState.COMPLETED, JobState.FAILED, JobState.CANCELED})

ALLOWED_TRANSITIONS: Mapping[JobState, frozenset[JobState]] = {
    JobState.REGISTERED: frozenset({JobState.VALIDATING_INPUT, JobState.CANCELED}),
    JobState.QUEUED: frozenset({JobState.VALIDATING_INPUT, JobState.CANCELED}),
    JobState.VALIDATING_INPUT: frozenset({JobState.READY_FOR_GENERATION, JobState.GENERATING_MASTER, JobState.FAILED, JobState.CANCELED}),
    JobState.READY_FOR_GENERATION: frozenset({JobState.VALIDATING_INPUT, JobState.CANCELED}),
    JobState.GENERATING_MASTER: frozenset({JobState.AWAITING_MASTER_APPROVAL, JobState.FAILED, JobState.CANCELED}),
    JobState.AWAITING_MASTER_APPROVAL: frozenset({JobState.CONSISTENCY_TEST, JobState.CANCELED}),
    JobState.CONSISTENCY_TEST: frozenset({JobState.READY_FOR_POSES, JobState.CONSISTENCY_FAILED, JobState.FAILED, JobState.CANCELED}),
    JobState.CONSISTENCY_FAILED: frozenset({JobState.GENERATING_MASTER, JobState.CANCELED}),
    JobState.READY_FOR_POSES: frozenset({JobState.GENERATING_POSES, JobState.CANCELED}),
    JobState.GENERATING_POSES: frozenset({JobState.COMPLETED, JobState.FAILED, JobState.CANCELED}),
    JobState.COMPLETED: frozenset(),
    JobState.FAILED: frozenset(),
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
    attempt_id: str | None = None
    state: JobState = JobState.QUEUED
    master_id: str | None = None
    pose_set_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    model_version: str = "qwen-image-edit-2511"
    prompt_version: str = MASTER_PROMPT_VERSION
    template_version: str = POSE_TEMPLATE_VERSION
    pose_choices: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_POSE_CHOICES))
    subject_identity: dict[str, object] = field(default_factory=lambda: {
        "category": "other",
        "label": "confirmed subject",
        "species": None,
    })
    correlation_id: str | None = None
    attempts: int = 0
    error_code: str | None = None
    generation_reserved: bool = False
    gpu_call_id: str | None = None
    pose_gpu_call_id: str | None = None
    pose_operation_id: str | None = None
    pose_operation_fingerprint: str | None = None
    pose_operation_status: str | None = None
    pose_operation_created_at: str | None = None
    pose_request_id: str | None = None

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
        self.transition_to(JobState.CONSISTENCY_TEST)
        return True

    def start_pose_generation(self) -> bool:
        if self.state is JobState.GENERATING_POSES:
            return False
        if self.state is not JobState.CONSISTENCY_TEST:
            raise DomainError("Pose generation is not available for this job.")
        self.transition_to(JobState.READY_FOR_POSES)
        self.transition_to(JobState.GENERATING_POSES)
        return True

    def complete_pose_generation(self, pose_set_id: str) -> bool:
        if self.state is JobState.COMPLETED:
            return False
        if self.state is not JobState.GENERATING_POSES:
            raise DomainError("Pose generation is not active for this job.")
        self.pose_set_id = pose_set_id
        self.transition_to(JobState.COMPLETED)
        return True

    def cancel(self) -> bool:
        if self.state is JobState.CANCELED:
            return False
        if self.state in TERMINAL_STATES:
            return False
        self.transition_to(JobState.CANCELED)
        return True
