"""Stable public contract helpers for Puleiro's Modal v2 integration."""

from __future__ import annotations

from modal_service.domain import JobRecord, JobState


PUBLIC_STATUS_BY_STATE = {
    JobState.REGISTERED: "registered",
    JobState.QUEUED: "queued",
    JobState.VALIDATING_INPUT: "queued",
    JobState.READY_FOR_GENERATION: "awaiting_generation_authorization",
    JobState.GENERATING_MASTER: "generating_masters",
    JobState.AWAITING_MASTER_APPROVAL: "awaiting_master_approval",
    JobState.CONSISTENCY_TEST: "master_approved",
    JobState.CONSISTENCY_FAILED: "failed",
    JobState.READY_FOR_POSES: "master_approved",
    JobState.GENERATING_POSES: "generating_poses",
    JobState.COMPLETED: "awaiting_set_approval",
    JobState.FAILED: "failed",
    JobState.CANCELED: "canceled",
}


def public_job(
    job: JobRecord,
    masters: list[dict[str, str]] | None = None,
    poses: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    status = PUBLIC_STATUS_BY_STATE[job.state]
    payload: dict[str, object] = {
        "jobId": job.job_id,
        "attemptId": job.attempt_id,
        "status": status,
        "generationScheduled": job.state not in {JobState.REGISTERED, JobState.READY_FOR_GENERATION},
        "createdAt": job.created_at,
        "updatedAt": job.updated_at,
        "subjectIdentity": job.subject_identity,
        "poseChoices": job.pose_choices,
    }
    if status == "awaiting_master_approval":
        payload["masters"] = masters or []
    if status == "awaiting_set_approval":
        payload["poses"] = poses or []
    if job.master_id:
        payload["approvedMasterId"] = job.master_id
    if job.error_code:
        payload["error"] = {"code": job.error_code}
    return payload
