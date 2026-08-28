from modal_service.app import _new_pose_smoke_job, _pose_smoke_job_id, _pose_smoke_key
from modal_service.domain import JobRecord, JobState


def test_pose_smoke_clone_is_deterministic_and_never_reuses_completed_pose_state():
    source = JobRecord(
        job_id="job_source",
        user_id="owner",
        idempotency_key="source-key",
        source_key="original/hash",
        state=JobState.COMPLETED,
        master_id="master_1",
        display_name="Mascote GRU",
        pose_operation_id="old-operation",
        pose_gpu_call_id="old-call",
        pose_generation_reserved=True,
    )

    target_id = _pose_smoke_job_id(source.job_id, "full-body-v6")
    clone = _new_pose_smoke_job(source, target_id, "full-body-v6")

    assert target_id == _pose_smoke_job_id(source.job_id, "full-body-v6")
    assert clone.state is JobState.CONSISTENCY_TEST
    assert clone.master_id == "master_1"
    assert clone.pose_operation_id is None
    assert clone.pose_gpu_call_id is None
    assert clone.pose_generation_reserved is False
    assert clone.idempotency_key == _pose_smoke_key(source.job_id, "full-body-v6")
    assert clone.pose_choices == source.pose_choices


def test_pose_smoke_clone_copies_configuration_without_mutating_source():
    source = JobRecord(
        job_id="job_source",
        user_id="owner",
        idempotency_key="source-key",
        source_key="original/hash",
        state=JobState.COMPLETED,
        master_id="master_1",
        pose_choices={"normal": "normal_attentive", "listening": "listening_natural", "transcribing": "transcribing_active"},
    )

    clone = _new_pose_smoke_job(source, "job_clone", "once")
    clone.pose_choices["normal"] = "normal_relaxed"

    assert source.pose_choices["normal"] == "normal_attentive"
