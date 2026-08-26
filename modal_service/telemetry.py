"""Privacy-preserving generation telemetry shared by Modal workers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from modal_service.domain import JobRecord


def generation_event(
    job: JobRecord,
    event_name: str,
    stage: str,
    outcome: str,
    *,
    duration_ms: int | None = None,
    reserved_cost_usd: float | None = None,
    estimated_cost_usd: float | None = None,
    gpu_elapsed_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Build a bounded event payload without user identifiers or image data."""
    payload: dict[str, object] = {
        "trace_id": job.trace_id,
        "modal_job_id": job.job_id,
        "event_name": event_name,
        "stage": stage,
        "outcome": outcome,
        "occurred_at": datetime.now(UTC).isoformat(),
        "model_version": job.model_version,
        "prompt_version": job.prompt_version,
    }
    if duration_ms is not None:
        payload["duration_ms"] = max(0, duration_ms)
    if reserved_cost_usd is not None:
        payload["reserved_cost_usd"] = max(0.0, reserved_cost_usd)
    if estimated_cost_usd is not None:
        payload["estimated_cost_usd"] = max(0.0, estimated_cost_usd)
    if gpu_elapsed_ms is not None:
        payload["gpu_elapsed_ms"] = max(0, gpu_elapsed_ms)
    if metadata:
        payload["metadata"] = _safe_metadata(metadata)
    return payload


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    safe: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if key in {"user_id", "token", "authorization", "source_key", "prompt"}:
            continue
        if not isinstance(value, (str, int, float, bool)):
            continue
        safe[str(key)[:64]] = value if not isinstance(value, str) else value[:128]
    return safe
