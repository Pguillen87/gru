"""Sanitized JSON events shared by the HTTP boundary and asynchronous workers."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any


ALLOWED_FIELDS = frozenset(
    {
        "timestamp", "environment", "service", "event", "result", "durationMs",
        "puleiroTraceId", "attemptId", "operationId", "requestId", "jobId",
        "masterId", "poseRole", "safeErrorCode", "httpStatus",
    }
)


def structured_event(event: str, **fields: Any) -> None:
    payload: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "gru-modal",
        "event": _safe_text(event, 64),
    }
    for key, value in fields.items():
        if key in ALLOWED_FIELDS and _safe_value(value):
            payload[key] = value
    logging.info("modal_event %s", json.dumps(payload, separators=(",", ":"), sort_keys=True))


def _safe_text(value: str, limit: int) -> str:
    normalized = "".join(character for character in value if character.isalnum() or character in "._:-")
    return normalized[:limit] or "unknown"


def _safe_value(value: Any) -> bool:
    if value is None or isinstance(value, (bool, int, float)):
        return True
    return isinstance(value, str) and len(value) <= 160 and all(
        character.isalnum() or character in "._:-" for character in value
    )
