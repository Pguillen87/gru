"""Durable filesystem outbox for privacy-safe generation telemetry."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from uuid import uuid4


MAX_DELIVERY_ATTEMPTS = 10


def enqueue(root: Path, payload: dict[str, object]) -> dict[str, object]:
    event = dict(payload)
    event.setdefault("event_id", str(uuid4()))
    event["delivery_attempt"] = 0
    envelope = {"payload": event, "next_attempt_at": 0.0, "last_error_class": None}
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{event['event_id']}.json"
    temporary = root / f".{event['event_id']}.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(envelope, separators=(",", ":")), encoding="utf-8")
    temporary.replace(target)
    return event


def due_files(root: Path, *, now: float | None = None, limit: int = 100) -> list[Path]:
    instant = time.time() if now is None else now
    due: list[Path] = []
    for path in sorted(root.glob("*.json")):
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if not envelope.get("exhausted", False) and float(envelope.get("next_attempt_at", 0)) <= instant:
                due.append(path)
        except (OSError, ValueError, TypeError):
            continue
        if len(due) >= limit:
            break
    return due


def load(path: Path) -> tuple[dict[str, object], int]:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    payload = dict(envelope["payload"])
    attempt = int(payload.get("delivery_attempt", 0)) + 1
    payload["delivery_attempt"] = attempt
    return payload, attempt


def record_failure(path: Path, payload: dict[str, object], attempt: int, error_class: str, *, now: float | None = None) -> None:
    delay = min(60 * (2 ** max(0, attempt - 1)), 6 * 60 * 60)
    envelope = {
        "payload": payload,
        "next_attempt_at": (time.time() if now is None else now) + delay,
        "last_error_class": error_class[:128],
        "exhausted": attempt >= MAX_DELIVERY_ATTEMPTS,
    }
    path.write_text(json.dumps(envelope, separators=(",", ":")), encoding="utf-8")


def pending_count(root: Path) -> int:
    return sum(1 for _ in root.glob("*.json")) if root.is_dir() else 0
