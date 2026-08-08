import json

from modal_service.inference_observability import InferenceObserver, trace_id_for_job


class CapturingLogger:
    def __init__(self):
        self.messages = []

    def info(self, template, payload):
        self.messages.append(template % payload)


def test_trace_id_is_stable_and_does_not_expose_job_id():
    trace = trace_id_for_job("job_private_reference")

    assert trace == trace_id_for_job("job_private_reference")
    assert len(trace) == 12
    assert "private" not in trace


def test_observer_emits_only_allowlisted_sanitized_fields():
    logger = CapturingLogger()
    observer = InferenceObserver("trace123", logger=logger)

    observer.event(
        "job_started",
        {
            "cold_start": True,
            "source_bytes": 42,
            "firebase_uid": "must-not-appear",
            "authorization": "must-not-appear",
            "error_type": "Unsafe value with spaces",
        },
    )
    payload = json.loads(logger.messages[0].removeprefix("modal_inference "))

    assert payload == {
        "cold_start": True,
        "event": "job_started",
        "source_bytes": 42,
        "trace_id": "trace123",
    }
