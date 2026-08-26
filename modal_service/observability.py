"""Privacy-safe structured logging for Modal functions."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any


_BLOCKED_KEYS = {"authorization", "image", "image_base64", "prompt", "source_key", "token", "user_id"}


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    payload: dict[str, Any] = {"event": event, "timestamp": datetime.now(UTC).isoformat()}
    for key, value in fields.items():
        if key in _BLOCKED_KEYS or value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            payload[key] = value if not isinstance(value, str) else value[:256]
    logging.log(level, json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
