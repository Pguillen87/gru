"""Sanitized, structured observability for Modal inference workers."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable, Mapping
from typing import Any


ALLOWED_FIELDS = frozenset(
    {
        "cache_revision",
        "cache_validation_ms",
        "cold_start",
        "container_reused",
        "container_start_ms",
        "cuda_transfer_ms",
        "error_code",
        "error_type",
        "generation_ms",
        "gpu_peak_memory_bytes",
        "gpu_type",
        "inference_config_hash",
        "jobs_in_container",
        "lora_load_ms",
        "master_index",
        "model_read_ms",
        "outcome",
        "outputs",
        "pipeline_build_ms",
        "postprocess_ms",
        "result_bytes",
        "result_write_ms",
        "source_bytes",
        "source_height",
        "source_width",
        "total_worker_ms",
        "worker_age_ms",
    }
)


def trace_id_for_job(job_id: str) -> str:
    """Return a stable correlation identifier without exposing the job or UID."""
    return hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:12]


class InferenceObserver:
    def __init__(
        self,
        trace_id: str,
        *,
        logger: logging.Logger | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.trace_id = trace_id
        self._logger = logger or logging.getLogger("gru.modal.inference")
        self._stdout = logger is None
        self._clock = clock

    def mark(self) -> float:
        return self._clock()

    def elapsed_ms(self, started_at: float) -> int:
        return max(0, int((self._clock() - started_at) * 1_000))

    def event(self, name: str, fields: Mapping[str, Any] | None = None) -> None:
        safe_fields = {
            key: value
            for key, value in (fields or {}).items()
            if key in ALLOWED_FIELDS and _safe_value(value)
        }
        payload = {"event": _event_name(name), "trace_id": self.trace_id, **safe_fields}
        serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        if self._stdout:
            print(f"modal_inference {serialized}", flush=True)
        else:
            self._logger.info("modal_inference %s", serialized)


def _event_name(value: str) -> str:
    normalized = "".join(
        character
        for character in value.lower()
        if character.isalnum() or character == "_"
    )
    return normalized[:64] or "unknown"


def _safe_value(value: Any) -> bool:
    if value is None or isinstance(value, (bool, int, float)):
        return True
    if isinstance(value, str):
        return len(value) <= 96 and all(
            character.isalnum() or character in "._:-" for character in value
        )
    return False
