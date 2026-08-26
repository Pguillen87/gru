"""Deterministic fixed-window limits used by the serialized Modal guard."""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class LimitDecision:
    allowed: bool
    retry_after_seconds: int
    remaining: int


def minute_window(now: datetime | None = None) -> tuple[str, int]:
    instant = (now or datetime.now(UTC)).astimezone(UTC)
    window = instant.replace(second=0, microsecond=0)
    retry_after = max(1, int((window + timedelta(minutes=1) - instant).total_seconds()))
    return window.isoformat(), retry_after


def consume_limit(store: MutableMapping[str, object], key: str, limit: int, *, now: datetime | None = None) -> LimitDecision:
    window, retry_after = minute_window(now)
    counter_key = f"rate:{window}:{key}"
    current = int(store.get(counter_key, 0))
    if current >= limit:
        return LimitDecision(False, retry_after, 0)
    next_value = current + 1
    store[counter_key] = next_value
    return LimitDecision(True, retry_after, max(0, limit - next_value))
