import json
from pathlib import Path

from modal_service.outbox import MAX_DELIVERY_ATTEMPTS, due_files, enqueue, load, pending_count, record_failure


def test_outbox_is_idempotently_addressed_and_retries(tmp_path: Path):
    event = enqueue(tmp_path, {"event_name": "job_registered"})
    path = tmp_path / f"{event['event_id']}.json"
    payload, attempt = load(path)
    record_failure(path, payload, attempt, "Timeout", now=100)
    assert due_files(tmp_path, now=159) == []
    assert due_files(tmp_path, now=160) == [path]
    assert pending_count(tmp_path) == 1


def test_exhausted_outbox_event_is_retained_but_not_redelivered(tmp_path: Path):
    event = enqueue(tmp_path, {"event_name": "job_registered"})
    path = tmp_path / f"{event['event_id']}.json"
    payload = dict(event)
    payload["delivery_attempt"] = MAX_DELIVERY_ATTEMPTS
    record_failure(path, payload, MAX_DELIVERY_ATTEMPTS, "Timeout", now=100)
    assert due_files(tmp_path, now=10_000_000) == []
    assert json.loads(path.read_text())["exhausted"] is True
    assert pending_count(tmp_path) == 1
