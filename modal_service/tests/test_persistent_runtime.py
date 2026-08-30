import pytest

from modal_service.persistent_runtime import PersistentPipelineRuntime, WorkerCorrupted


def test_pipeline_is_loaded_once_for_multiple_jobs():
    load_calls = 0

    def load_pipeline():
        nonlocal load_calls
        load_calls += 1
        return object()

    worker = PersistentPipelineRuntime(load_pipeline)
    worker.start()
    worker.run(lambda pipeline: pipeline)
    worker.run(lambda pipeline: pipeline)
    worker.run(lambda pipeline: pipeline)

    assert load_calls == 1
    assert worker.jobs_processed == 3


def test_failed_operation_marks_worker_as_not_reusable():
    worker = PersistentPipelineRuntime(object)

    with pytest.raises(RuntimeError, match="generation failed"):
        worker.run(
            lambda _pipeline: (_ for _ in ()).throw(RuntimeError("generation failed"))
        )

    assert not worker.healthy
    with pytest.raises(WorkerCorrupted):
        worker.run(lambda pipeline: pipeline)


def test_pipeline_load_failure_can_be_retried_before_any_job():
    calls = 0

    def loader():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("cache unavailable")
        return "pipeline"

    worker = PersistentPipelineRuntime(loader)
    with pytest.raises(RuntimeError):
        worker.start()

    assert worker.start() == "pipeline"
    assert calls == 2
