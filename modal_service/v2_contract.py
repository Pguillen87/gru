"""Stable public contract helpers for Puleiro's Modal v2 integration."""

from __future__ import annotations

from modal_service.domain import JobRecord, JobState
from modal_service.incubator import product_state


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


def ready_to_hatch_evidence(
    job: JobRecord,
    masters: list[dict[str, object]],
    poses: list[dict[str, object]],
    pose_set_qc: dict[str, object] | None,
    storage_verified: bool,
) -> bool:
    """Return true only when the complete, verified pose set is present.

    ``COMPLETED`` is an internal workflow state, not by itself proof that the
    public hatch contract is safe.  Callers must provide the result of the
    checksum/manifest verifier as ``storage_verified``.
    """
    if job.state is not JobState.COMPLETED or not job.generation_ready_at or not storage_verified:
        return False
    if not job.master_id or not any(item.get("id") == job.master_id for item in masters):
        return False
    if len(poses) != 3 or {item.get("role") for item in poses} != {"normal", "listening", "transcribing"}:
        return False
    if any(not isinstance(item.get("qc"), dict) or item["qc"].get("status") != "passed" for item in poses):
        return False
    return bool(isinstance(pose_set_qc, dict) and pose_set_qc.get("status") == "passed"
                and pose_set_qc.get("version") == "pose-set-visual-v3")


def public_job(
    job: JobRecord,
    masters: list[dict[str, object]] | None = None,
    poses: list[dict[str, object]] | None = None,
    pose_set_qc: dict[str, object] | None = None,
    ready_evidence: bool = False,
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
        "configuration": {
            "displayName": job.display_name,
            "poseChoices": job.pose_choices,
            "configurationRevision": job.configuration_revision,
        },
        "workflowMode": job.workflow_mode,
        "productState": "READY_TO_HATCH" if ready_evidence else product_state(job),
    }
    if status == "awaiting_master_approval":
        payload["masters"] = masters or []
    if status == "awaiting_set_approval":
        payload["poses"] = poses or []
        payload["poseSetQc"] = pose_set_qc or {
            "status": "failed",
            "code": "VISUAL_POSE_CONSISTENCY_UNAVAILABLE",
            "version": "pose-set-visual-v1",
            "safe_reasons": ["POSE_SET_QC_UNAVAILABLE"],
        }
    if job.master_id:
        payload["approvedMasterId"] = job.master_id
    if job.error_code:
        payload["error"] = {"code": job.error_code}
    if job.pose_operation_id:
        payload["operationId"] = job.pose_operation_id
    if job.subject_hint:
        payload["subjectHint"] = job.subject_hint
    if job.master_selection:
        payload["masterSelection"] = job.master_selection
    if job.generation_ready_at:
        payload["generationReadyAt"] = job.generation_ready_at
    return payload
