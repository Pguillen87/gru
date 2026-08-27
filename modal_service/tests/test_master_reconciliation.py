from datetime import UTC, datetime, timedelta
from pathlib import Path

from modal_service import app
from modal_service.config import limits_for
from modal_service.coordinator import JobCoordinator
from modal_service.domain import JobRecord, JobState


def _job(
    state: JobState = JobState.GENERATING_MASTER, *, age_seconds: int = 0
) -> JobRecord:
    return JobRecord(
        job_id="job_test",
        user_id="user",
        idempotency_key="key",
        source_key="source",
        state=state,
        updated_at=(datetime.now(UTC) - timedelta(seconds=age_seconds)).isoformat(),
    )


def test_master_outputs_ready_requires_every_nonempty_file(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "ASSET_ROOT", str(tmp_path))
    job = _job()
    target = tmp_path / "masters" / job.job_id
    target.mkdir(parents=True)

    for index in range(1, 4):
        (target / f"master_{index}.png").write_bytes(b"png")
    assert app._master_outputs_ready(job)

    (target / "master_2.png").write_bytes(b"")
    assert not app._master_outputs_ready(job)


def test_public_master_references_are_limited_to_the_three_seed_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "ASSET_ROOT", str(tmp_path))
    job = _job(JobState.AWAITING_MASTER_APPROVAL)
    target = tmp_path / "masters" / job.job_id
    target.mkdir(parents=True)
    for index in range(1, 5):
        (target / f"master_{index}.png").write_bytes(b"png")

    assert [item["id"] for item in app._master_references(job)] == ["master_1", "master_2", "master_3"]


def test_reconciliation_waits_before_checking_worker_result():
    assert not app._should_reconcile_master(_job(age_seconds=14))
    assert app._should_reconcile_master(_job(age_seconds=16))
    assert not app._should_reconcile_master(
        _job(JobState.AWAITING_MASTER_APPROVAL, age_seconds=60)
    )


def test_deserialize_ignores_master_references_added_for_api_responses(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "ASSET_ROOT", str(tmp_path))
    job = _job(JobState.AWAITING_MASTER_APPROVAL)
    target = tmp_path / "masters" / job.job_id
    target.mkdir(parents=True)
    (target / "master_1.png").write_bytes(b"png")

    restored = app._deserialize(app._serialize(job))

    assert restored == job


def test_result_asset_refresh_only_runs_for_states_that_expose_worker_outputs(monkeypatch):
    reload_calls = 0

    def reload_assets():
        nonlocal reload_calls
        reload_calls += 1

    monkeypatch.setattr(app.assets, "reload", reload_assets)

    app._refresh_result_assets(_job(JobState.GENERATING_MASTER))
    app._refresh_result_assets(_job(JobState.AWAITING_MASTER_APPROVAL))

    assert reload_calls == 1


def test_stale_worker_failure_is_idempotent():
    job = _job(age_seconds=301)
    store = {job.job_id: {**job.__dict__, "state": job.state.value}}
    coordinator = JobCoordinator(store, {}, {}, limits_for("development"), "2026-08-08")

    failed, changed = coordinator.fail_stale_master(job.job_id, "MASTER_WORKER_STALE")
    repeated, changed_again = coordinator.fail_stale_master(
        job.job_id, "MASTER_WORKER_STALE"
    )

    assert changed
    assert failed.state is JobState.FAILED
    assert failed.error_code == "MASTER_WORKER_STALE"
    assert not changed_again
    assert repeated.state is JobState.FAILED


def test_gpu_worker_persists_before_small_commit():
    source = Path(app.__file__).read_text(encoding="utf-8")
    generate_body = source.split("def generate(self, job_id: str)", 1)[1].split(
        "@modal.exit()", 1
    )[0]

    assert "_persist_master_outputs(job, outputs)" in generate_body
    assert "outputs=outputs" not in generate_body
    assert generate_body.index("assets.reload()") < generate_body.index("_generate_qwen_masters")
