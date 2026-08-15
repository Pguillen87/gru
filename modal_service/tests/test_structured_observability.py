from __future__ import annotations

import json
import logging

from modal_service.structured_observability import structured_event


def test_structured_event_is_json_and_drops_sensitive_fields(caplog):
    with caplog.at_level(logging.INFO):
        structured_event(
            "pose_request_received",
            requestId="request-1",
            jobId="job-1",
            token="secret-token",
            cookie="secret-cookie",
            image="base64-data",
            prompt="private prompt",
        )

    line = next(record.message for record in caplog.records if record.message.startswith("modal_event "))
    payload = json.loads(line.removeprefix("modal_event "))
    assert payload["service"] == "gru-modal"
    assert payload["requestId"] == "request-1"
    assert payload["jobId"] == "job-1"
    assert {"token", "cookie", "image", "prompt"}.isdisjoint(payload)
