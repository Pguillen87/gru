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
