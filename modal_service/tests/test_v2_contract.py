from __future__ import annotations

from pathlib import Path

from modal_service.domain import JobRecord, JobState
from modal_service.v2_contract import public_job


def record(state: JobState, **values) -> JobRecord:
    return JobRecord(
        job_id="job-1",
        user_id="uid-1",
        idempotency_key="key-1",
        source_key="original/hash",
        attempt_id="attempt-1",
        state=state,
        **values,
    )


def test_registered_job_is_public_and_never_claims_generation_scheduled():
    payload = public_job(record(JobState.REGISTERED))
    assert payload["status"] == "registered"
    assert payload["generationScheduled"] is False
    assert "user_id" not in payload and "source_key" not in payload


def test_completed_modal_step_is_not_publicly_ready():
    assert public_job(record(JobState.COMPLETED))["status"] == "awaiting_set_approval"


def test_public_states_needed_for_no_gpu_simulation_are_stable():
    assert public_job(record(JobState.AWAITING_MASTER_APPROVAL))["status"] == "awaiting_master_approval"
    assert public_job(record(JobState.READY_FOR_POSES, master_id="master_1"))["status"] == "master_approved"
    assert public_job(record(JobState.FAILED, error_code="SIMULATED"))["status"] == "failed"
    assert public_job(record(JobState.CANCELED))["status"] == "canceled"


def test_approval_and_registration_v2_do_not_spawn_gpu_or_poses():
    source = Path("modal_service/app.py").read_text(encoding="utf-8")
    create_block = source.split('@service.post("/v2/mascot/jobs", status_code=202)', 1)[1].split(
        '@service.get("/v2/mascot/jobs")', 1
    )[0]
    approval_block = source.split(
        '@service.post("/v2/mascot/jobs/{job_id}/masters/{master_id}/approve")', 1
    )[1].split('@service.post("/v2/mascot/jobs/{job_id}/pose-generations"', 1)[0]

    assert ".spawn(" not in create_block
    assert "_schedule_master" not in create_block
    assert ".generate_poses.spawn(" not in approval_block
    assert "START_POSES" not in approval_block


def test_v1_routes_remain_in_the_api_factory():
    source = Path("modal_service/app.py").read_text(encoding="utf-8")
    assert '@service.post("/v1/mascot/jobs"' in source
    assert '@service.post("/v1/mascot/jobs/{job_id}/approve-master"' in source
    assert '@service.get("/v1/mascot/jobs/{job_id}/result"' in source


def test_v2_master_download_is_owner_scoped():
    source = Path("modal_service/app.py").read_text(encoding="utf-8")
    route = source.split('@service.get("/v2/mascot/jobs/{job_id}/masters/{master_id}")', 1)[1]
    route = route.split('@service.post("/v2/mascot/jobs/{job_id}/pose-generations"', 1)[0]
    assert "verified_bff_identity" in route
    assert "_ensure_owner(job, identity.user_id)" in route
