from modal_service.domain import BenchmarkScore, DomainError, JobNotFound, JobRecord, JobState


def test_job_rejects_impossible_transition():
    job = JobRecord("job", "user", "key", "originals/input.png")
    try:
        job.transition_to(JobState.COMPLETED)
    except DomainError:
        return
    raise AssertionError("impossible transition was accepted")


def test_score_requires_identity_gate():
    score = BenchmarkScore(8.9, 10, 10, 10, 10, 10)
    assert score.total() > 8.2
    assert not score.passes()


def test_missing_job_has_safe_public_code():
    assert JobNotFound.code == "JOB_NOT_FOUND"


def test_master_approval_is_idempotent_after_response_loss():
    job = JobRecord("job", "user", "key", "source", state=JobState.AWAITING_MASTER_APPROVAL)
    assert job.approve_master("master_1")
    assert not job.approve_master("master_1")
    assert job.state is JobState.CONSISTENCY_TEST


def test_different_master_is_rejected_after_approval():
    job = JobRecord("job", "user", "key", "source", state=JobState.AWAITING_MASTER_APPROVAL)
    job.approve_master("master_1")
    try:
        job.approve_master("master_2")
    except DomainError:
        return
    raise AssertionError("different master was accepted")


def test_cancel_is_idempotent():
    job = JobRecord("job", "user", "key", "source", state=JobState.READY_FOR_GENERATION)
    assert job.cancel()
    assert not job.cancel()


def test_approved_master_can_generate_and_complete_selected_poses():
    job = JobRecord("job", "user", "key", "source", state=JobState.AWAITING_MASTER_APPROVAL)

    job.approve_master("master_1")
    assert job.start_pose_generation()
    assert job.state is JobState.GENERATING_POSES
    assert job.complete_pose_generation("job")
    assert job.state is JobState.COMPLETED
    assert job.pose_set_id == "job"
