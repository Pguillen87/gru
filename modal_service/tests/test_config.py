from pathlib import Path

import pytest

import modal_service.app as mascot_app
from modal_service.config import Environment, generation_enabled, limits_for
from modal_service.domain import JobRecord, JobState, WorkflowMode
from modal_service.app import (
    GuardRejected,
    MASTER_SEEDS,
    PERSISTENT_WORKER_MAX_CONTAINERS,
    WORKER_SCALEDOWN_SECONDS,
    _spawn_master_worker,
    _spawn_pose_worker,
    inference_config_hash,
)


def test_generation_is_disabled_by_default_in_every_environment():
    assert all(not limits_for(environment).generation_enabled for environment in Environment)
    assert not hasattr(limits_for(Environment.PRODUCTION), "max_retries_per_pose")


def test_generation_requires_explicit_true_override():
    assert not generation_enabled(Environment.DEVELOPMENT)
    assert not generation_enabled(Environment.DEVELOPMENT, "false")
    assert generation_enabled(Environment.DEVELOPMENT, "true")


def test_auto_ranking_is_fail_closed_and_shadow_mode_cannot_select_or_start_poses():
    assert mascot_app.INCUBATOR_AUTO_RANKING_ENABLED is False
    source = Path("modal_service/app.py").read_text(encoding="utf-8")
    advance = source.split("def advance_async_incubation", 1)[1].split("def reconcile_async_incubations", 1)[0]
    shadow_gate = advance.index("if not INCUBATOR_AUTO_RANKING_ENABLED:")
    selection = advance.index("JobOperation.AUTO_SELECT_MASTER")
    pose_reservation = advance.index("JobOperation.ENQUEUE_POSES")
    assert shadow_gate < selection < pose_reservation
    shadow_block = advance[shadow_gate:selection]
    assert "incubator_master_ranked_shadow" in shadow_block
    assert '"deferred": True' in shadow_block


def test_development_guard_is_single_container_with_workspace_credit_ceiling():
    limits = limits_for(Environment.DEVELOPMENT)
    assert limits.max_containers == 1
    assert limits.daily_cost_cap_usd == 30.0
    assert limits.jobs_per_user_per_day == 100
    assert limits.generations_per_user_per_day == 30
    assert limits.global_jobs_per_day == 100


def test_persistent_worker_preserves_approved_generation_identity():
    assert MASTER_SEEDS == (0, 1, 2)
    assert PERSISTENT_WORKER_MAX_CONTAINERS == 1
    assert WORKER_SCALEDOWN_SECONDS == 45
    assert inference_config_hash() == "f686a19c27ae3a2c"


class _FakeSpawn:
    def __init__(self) -> None:
        self.calls = 0

    def spawn(self, job_id: str) -> object:
        del job_id
        self.calls += 1
        return object()


class _FakeWorker:
    def __init__(self, master: _FakeSpawn, poses: _FakeSpawn) -> None:
        self.generate = master
        self.generate_poses = poses


@pytest.mark.parametrize(
    ("gpu_enabled", "master_enabled", "expected_spawns"),
    [(False, True, 0), (True, False, 0), (True, True, 1)],
)
def test_master_spawn_boundary_requires_both_generation_flags(
    monkeypatch, gpu_enabled: bool, master_enabled: bool, expected_spawns: int
):
    master, poses = _FakeSpawn(), _FakeSpawn()
    monkeypatch.setattr(mascot_app, "GPU_GENERATION_ENABLED", gpu_enabled)
    monkeypatch.setattr(mascot_app, "MASTER_GENERATION_ENABLED", master_enabled)
    monkeypatch.setattr(mascot_app, "QwenMasterWorker", lambda: _FakeWorker(master, poses))

    if expected_spawns:
        _spawn_master_worker("job-incubator")
    else:
        with pytest.raises(GuardRejected, match="Master generation is disabled"):
            _spawn_master_worker("job-incubator")

    assert master.calls == expected_spawns
    assert poses.calls == 0


@pytest.mark.parametrize(
    ("gpu_enabled", "pose_enabled", "expected_spawns"),
    [(False, True, 0), (True, False, 0), (True, True, 1)],
)
def test_pose_spawn_boundary_requires_both_generation_flags(
    monkeypatch, gpu_enabled: bool, pose_enabled: bool, expected_spawns: int
):
    master, poses = _FakeSpawn(), _FakeSpawn()
    monkeypatch.setattr(mascot_app, "GPU_GENERATION_ENABLED", gpu_enabled)
    monkeypatch.setattr(mascot_app, "POSE_GENERATION_ENABLED", pose_enabled)
    monkeypatch.setattr(mascot_app, "QwenMasterWorker", lambda: _FakeWorker(master, poses))

    if expected_spawns:
        _spawn_pose_worker("job-incubator")
    else:
        with pytest.raises(GuardRejected, match="Pose generation is disabled"):
            _spawn_pose_worker("job-incubator")

    assert poses.calls == expected_spawns
    assert master.calls == 0


def test_reconciler_defers_disabled_incubator_gpu_and_resumes_once(monkeypatch):
    job = JobRecord(
        "job-incubator",
        "owner",
        "key",
        "original/source",
        workflow_mode=WorkflowMode.ASYNC_INCUBATOR_V1.value,
        state=JobState.AWAITING_MASTER_APPROVAL,
    )
    records = {job.job_id: mascot_app._serialize(job)}
    calls = 0

    class _DeferredAdvance:
        def remote(self, job_id: str) -> dict[str, object]:
            nonlocal calls
            calls += 1
            records[job_id]["state"] = JobState.GENERATING_POSES.value
            return {"changed": True, "reserved": True}

    monkeypatch.setattr(mascot_app, "jobs", records)
    monkeypatch.setattr(mascot_app, "advance_async_incubation", _DeferredAdvance())
    monkeypatch.setattr(mascot_app, "GPU_GENERATION_ENABLED", False)
    monkeypatch.setattr(mascot_app, "POSE_GENERATION_ENABLED", True)

    mascot_app.reconcile_async_incubations.local()
    mascot_app.reconcile_async_incubations.local()
    assert calls == 0

    monkeypatch.setattr(mascot_app, "GPU_GENERATION_ENABLED", True)
    mascot_app.reconcile_async_incubations.local()
    mascot_app.reconcile_async_incubations.local()
    assert calls == 1


def test_reconciler_defers_disabled_master_without_reservation(monkeypatch):
    job = JobRecord(
        "job-incubator-master",
        "owner",
        "key",
        "original/source",
        workflow_mode=WorkflowMode.ASYNC_INCUBATOR_V1.value,
        state=JobState.REGISTERED,
    )
    records = {job.job_id: mascot_app._serialize(job)}
    calls = 0

    def schedule_once(current: JobRecord, user_id: str) -> dict[str, object]:
        nonlocal calls
        assert current.job_id == job.job_id and user_id == "owner"
        calls += 1
        records[job.job_id]["state"] = JobState.GENERATING_MASTER.value
        return records[job.job_id]

    monkeypatch.setattr(mascot_app, "jobs", records)
    monkeypatch.setattr(mascot_app, "_schedule_master", schedule_once)
    monkeypatch.setattr(mascot_app, "GPU_GENERATION_ENABLED", False)
    monkeypatch.setattr(mascot_app, "MASTER_GENERATION_ENABLED", True)

    mascot_app.reconcile_async_incubations.local()
    mascot_app.reconcile_async_incubations.local()
    assert calls == 0

    monkeypatch.setattr(mascot_app, "GPU_GENERATION_ENABLED", True)
    mascot_app.reconcile_async_incubations.local()
    mascot_app.reconcile_async_incubations.local()
    assert calls == 1
