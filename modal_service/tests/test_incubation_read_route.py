"""Run the nested route body without initializing cloud SDKs or scheduling work."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from modal_service import app
from modal_service.domain import JobNotFound, JobRecord, JobState, WorkflowMode


def read_handler(monkeypatch, job):
    tree = ast.parse(Path(app.__file__).read_text(encoding="utf-8"))
    route = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "read_job_v2")
    route.decorator_list = []
    route.args.defaults = []
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), route], type_ignores=[])
    ast.fix_missing_locations(module)
    monkeypatch.setattr(app, "_get_job", lambda _: job)
    monkeypatch.setattr(app, "_refresh_result_assets", lambda _: None)
    monkeypatch.setattr(app, "_public_job_with_assets", lambda value: {"jobId": value.job_id, "state": value.state.value})
    monkeypatch.setattr(app, "_api_error", lambda error: error)

    class NoScheduling:
        def remote(self, *_):
            pytest.fail("Reading a job must never schedule generation")

    monkeypatch.setattr(app, "advance_async_incubation", NoScheduling())
    namespace = dict(vars(app))
    exec(compile(module, app.__file__, "exec"), namespace)
    return namespace["read_job_v2"]


def test_get_returns_state_without_advancing_generation(monkeypatch):
    job = JobRecord("job", "owner", "key", "source", state=JobState.AWAITING_MASTER_APPROVAL,
                    workflow_mode=WorkflowMode.ASYNC_INCUBATOR_V1.value)
    result = asyncio.run(read_handler(monkeypatch, job)("job", SimpleNamespace(user_id="owner")))
    assert result == {"jobId": "job", "state": "AWAITING_MASTER_APPROVAL"}


def test_get_rejects_another_owner_before_returning_assets(monkeypatch):
    job = JobRecord("job", "owner", "key", "source")
    with pytest.raises(JobNotFound):
        asyncio.run(read_handler(monkeypatch, job)("job", SimpleNamespace(user_id="other")))
