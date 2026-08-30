"""Framework-independent lifecycle guard for a persistent inference pipeline."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar


PipelineT = TypeVar("PipelineT")
ResultT = TypeVar("ResultT")


class WorkerCorrupted(RuntimeError):
    code = "WORKER_CORRUPTED"


class PersistentPipelineRuntime(Generic[PipelineT]):
    def __init__(self, loader: Callable[[], PipelineT]) -> None:
        self._loader = loader
        self._pipeline: PipelineT | None = None
        self.jobs_processed = 0
        self.healthy = True

    def start(self) -> PipelineT:
        if self._pipeline is None:
            self._pipeline = self._loader()
        return self._pipeline

    def run(self, operation: Callable[[PipelineT], ResultT]) -> ResultT:
        if not self.healthy:
            raise WorkerCorrupted(
                "The inference worker must be replaced before accepting another job."
            )
        pipeline = self.start()
        try:
            result = operation(pipeline)
        except Exception:
            self.healthy = False
            raise
        self.jobs_processed += 1
        return result
