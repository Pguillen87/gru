from uuid import UUID

from modal_service.domain import JobRecord
from modal_service.telemetry import generation_event


def test_generation_event_has_stable_correlation_and_strips_sensitive_metadata():
    job = JobRecord("job_123", "firebase-user", "idempotency", "original/sha")

    event = generation_event(
        job,
        "master_worker_completed",
        "worker",
        "succeeded",
        duration_ms=125,
        reserved_cost_usd=0.2,
        metadata={"candidate_count": 3, "user_id": "must-not-leave-modal", "prompt": "private"},
    )

    assert UUID(str(event["trace_id"]))
    assert event["modal_job_id"] == "job_123"
    assert event["duration_ms"] == 125
    assert event["metadata"] == {"candidate_count": 3}
    assert "firebase-user" not in str(event)
