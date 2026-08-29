import pytest
from dataclasses import replace

from modal_service.config import Environment, limits_for
from modal_service.coordinator import JobCoordinator
from modal_service.costs import CostLimitExceeded, RateLimitExceeded
from modal_service.domain import DomainError, JobNotFound, JobState


def coordinator(*, limits=None):
    jobs, idempotency, usage = {}, {}, {}
    return JobCoordinator(jobs, idempotency, usage, limits or limits_for(Environment.DEVELOPMENT), "2026-08-03"), usage


def test_create_replay_returns_same_job_without_new_quota_or_cost():
    service, usage = coordinator()
    first, created = service.register("uid-a", "key-x", "original/hash")
    replay, replay_created = service.register("uid-a", "key-x", "original/hash")
    assert created and not replay_created
    assert replay.job_id == first.job_id
    assert usage["user-jobs:2026-08-03:uid-a"] == 1
    assert usage["global-jobs:2026-08-03"] == 1
    assert all("cost" not in key for key in usage)


def test_v2_registration_stops_before_generation_and_is_attempt_idempotent():
    service, usage = coordinator()
    first, created = service.register(
        "uid-a",
        "registration-key",
        "original/hash",
        registration_only=True,
        attempt_id="attempt-1",
    )
    replay, replay_created = service.register(
        "uid-a",
        "registration-key",
        "original/hash",
        registration_only=True,
        attempt_id="attempt-1",
    )

    assert created and not replay_created
    assert first.job_id == replay.job_id
    assert first.state is JobState.REGISTERED
    assert not first.generation_reserved and first.gpu_call_id is None
    assert all("cost" not in key for key in usage)


def test_v2_registration_persists_confirmed_subject_identity_and_rejects_replay_changes():
    service, _ = coordinator()
    identity = {"category": "human", "label": "person", "species": None}
    job, _ = service.register(
        "uid-a", "registration-key", "original/hash", subject_identity=identity,
        registration_only=True, attempt_id="attempt-1",
    )

    assert job.subject_identity == identity
    with pytest.raises(DomainError, match="different subject identity"):
        service.register(
            "uid-a", "registration-key", "original/hash",
            subject_identity={"category": "animal", "label": "dog", "species": "dog"},
            registration_only=True, attempt_id="attempt-1",
        )


def test_pose_generation_locks_exactly_one_choice_per_role():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    service.jobs[job.job_id]["state"] = JobState.CONSISTENCY_TEST.value
    choices = {
        "normal": "normal_relaxed",
        "listening": "listening_ready",
        "transcribing": "transcribing_notes",
    }

    started, changed = service.start_pose_generation(job.job_id, choices)

    assert changed and started.state is JobState.GENERATING_POSES
    assert started.pose_choices == choices


def test_configuration_is_owner_scoped_revisioned_and_does_not_start_gpu():
    service, usage = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    service.jobs[job.job_id]["state"] = JobState.CONSISTENCY_TEST.value
    choices = {
        "normal": "normal_relaxed",
        "listening": "listening_ready",
        "transcribing": "transcribing_notes",
    }

    updated, changed = service.update_configuration(job.job_id, "uid-a", "Paulinho", choices, 0)

    assert changed and updated.display_name == "Paulinho"
    assert updated.pose_choices == choices and updated.configuration_revision == 1
    assert all("cost" not in key for key in usage)
    replay, replay_changed = service.update_configuration(job.job_id, "uid-a", "Paulinho", choices, 0)
    assert not replay_changed and replay.configuration_revision == 1
    with pytest.raises(DomainError, match="another session"):
        service.update_configuration(job.job_id, "uid-a", "Outro", choices, 0)
    with pytest.raises(JobNotFound):
        service.update_configuration(job.job_id, "uid-b", None, choices, 1)


def test_pose_worker_call_is_reserved_once_and_then_recorded():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    service.jobs[job.job_id]["state"] = JobState.CONSISTENCY_TEST.value
    service.start_pose_generation(job.job_id, {
        "normal": "normal_relaxed",
        "listening": "listening_ready",
        "transcribing": "transcribing_notes",
    })

    reserved, changed = service.reserve_pose_gpu_call(job.job_id)
    repeated, repeated_changed = service.reserve_pose_gpu_call(job.job_id)
    recorded, recorded_changed = service.record_pose_gpu_call(job.job_id, "fc-pose")

    assert changed and reserved.pose_gpu_call_id == "reserved"
    assert not repeated_changed and repeated.pose_gpu_call_id == "reserved"
    assert recorded_changed and recorded.pose_gpu_call_id == "fc-pose"


def test_pose_qc_failure_transitions_the_active_job_to_failed_once():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    service.jobs[job.job_id]["state"] = JobState.CONSISTENCY_TEST.value
    service.jobs[job.job_id]["master_id"] = "master_1"
    service.start_pose_generation(job.job_id, {
        "normal": "normal_relaxed",
        "listening": "listening_ready",
        "transcribing": "transcribing_notes",
    })

    failed, changed = service.fail_pose_generation(job.job_id, "POSE_ALPHA_QC_FAILED")
    repeated, repeated_changed = service.fail_pose_generation(job.job_id, "POSE_ALPHA_QC_FAILED")

    assert changed and failed.state is JobState.FAILED
    assert failed.error_code == "POSE_ALPHA_QC_FAILED"
    assert failed.pose_operation_status == "failed"
    assert not repeated_changed and repeated.state is JobState.FAILED


def test_pose_operation_is_created_once_and_replayed_without_second_worker():
    service, usage = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    service.jobs[job.job_id]["state"] = JobState.CONSISTENCY_TEST.value
    service.jobs[job.job_id]["master_id"] = "master_1"
    choices = {
        "normal": "normal_relaxed",
        "listening": "listening_ready",
        "transcribing": "transcribing_notes",
    }

    first, created, reserved = service.enqueue_pose_generation(
        job.job_id, "uid-a", choices, "op-1", "fingerprint-1", "trace-1", "request-1"
    )
    replay, replay_created, replay_reserved = service.enqueue_pose_generation(
        job.job_id, "uid-a", choices, "op-2", "fingerprint-1", "trace-1", "request-2"
    )

    assert created and reserved
    assert not replay_created and not replay_reserved
    assert replay.pose_operation_id == first.pose_operation_id == "op-1"
    assert replay.pose_gpu_call_id == "reserved"
    assert replay.pose_generation_reserved
    assert usage["user-generations:2026-08-03:uid-a"] == 1
    assert usage["global-cost:2026-08-03"] == service.limits.estimated_generation_cost_usd


def test_pose_generation_cost_is_checked_before_a_worker_is_reserved():
    service, usage = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    job.state = JobState.CONSISTENCY_TEST
    job.master_id = "master_1"
    service.save(job)
    usage["global-cost:2026-08-03"] = service.limits.daily_cost_cap_usd

    with pytest.raises(CostLimitExceeded):
        service.enqueue_pose_generation(
            job.job_id,
            "uid-a",
            {"normal": "normal_relaxed", "listening": "listening_ready", "transcribing": "transcribing_notes"},
            "op-1",
            "fingerprint-1",
            "trace-1",
            "request-1",
        )

    unchanged = service.get(job.job_id)
    assert unchanged.state is JobState.CONSISTENCY_TEST
    assert unchanged.pose_operation_id is None
    assert unchanged.pose_gpu_call_id is None


def test_pose_operation_rejects_owner_and_choice_changes_after_reservation():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    service.jobs[job.job_id]["state"] = JobState.CONSISTENCY_TEST.value
    service.jobs[job.job_id]["master_id"] = "master_1"
    choices = {
        "normal": "normal_relaxed",
        "listening": "listening_ready",
        "transcribing": "transcribing_notes",
    }
    service.enqueue_pose_generation(
        job.job_id, "uid-a", choices, "op-1", "fingerprint-1", "trace-1", "request-1"
    )

    with pytest.raises(JobNotFound):
        service.enqueue_pose_generation(
            job.job_id, "uid-b", choices, "op-2", "fingerprint-1", "trace-2", "request-2"
        )
    with pytest.raises(DomainError, match="cannot change"):
        service.enqueue_pose_generation(
            job.job_id,
            "uid-a",
            choices | {"normal": "normal_attentive"},
            "op-2",
            "fingerprint-2",
            "trace-1",
            "request-2",
        )


def test_v2_attempt_is_owner_scoped_and_cannot_change_on_replay():
    service, _ = coordinator()
    job, _ = service.register(
        "uid-a", "registration-key", "original/hash", registration_only=True, attempt_id="attempt-1"
    )
    with pytest.raises(JobNotFound):
        service.ensure_owner(job, "uid-b")
    with pytest.raises(DomainError, match="different attempt"):
        service.register(
            "uid-a", "registration-key", "original/hash", registration_only=True, attempt_id="attempt-2"
        )


def test_delete_is_owner_scoped_and_removes_job_idempotency_entries():
    service, _ = coordinator()
    job, _ = service.register(
        "uid-a", "registration-key", "original/hash", registration_only=True, attempt_id="attempt-1"
    )

    with pytest.raises(JobNotFound):
        service.delete(job.job_id, "uid-b")

    deleted = service.delete(job.job_id, "uid-a")
    assert deleted.job_id == job.job_id
    assert job.job_id not in service.jobs
    assert all(value != job.job_id for value in service.idempotency.values())


def test_v2_generation_is_not_authorized_when_switch_is_off():
    service, usage = coordinator()
    job, _ = service.register(
        "uid-a", "registration-key", "original/hash", registration_only=True, attempt_id="attempt-1"
    )

    assert not service.authorize_generation(job.job_id, "uid-a", enabled=False)
    assert service.get(job.job_id).state is JobState.REGISTERED
    assert all("cost" not in key for key in usage)


def test_response_loss_recovery_uses_deterministic_job_without_new_quota():
    service, usage = coordinator()
    first, _ = service.register("uid-a", "key-x", "original/hash")
    service.idempotency.clear()
    replay, created = service.register("uid-a", "key-x", "original/hash")
    assert not created and replay.job_id == first.job_id
    assert usage["user-jobs:2026-08-03:uid-a"] == 1
    assert usage["global-jobs:2026-08-03"] == 1


def test_replay_rejects_a_different_image_for_the_same_key():
    service, _ = coordinator()
    service.register("uid-a", "key-x", "original/first")
    with pytest.raises(DomainError, match="different input"):
        service.register("uid-a", "key-x", "original/second")


def test_replay_rejects_different_pose_choices_for_the_same_key():
    service, _ = coordinator()
    first = {"normal": "normal_attentive", "listening": "listening_focus", "transcribing": "transcribing_fast"}
    second = first | {"normal": "normal_relaxed"}
    service.register("uid-a", "key-x", "original/first", first)

    with pytest.raises(DomainError, match="different pose choices"):
        service.register("uid-a", "key-x", "original/first", second)


def test_different_uid_cannot_read_job_metadata():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    with pytest.raises(JobNotFound):
        service.ensure_owner(job, "uid-b")


def test_disabled_generation_has_no_cost_and_keeps_ready_state():
    service, usage = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    assert not service.authorize_generation(job.job_id, "uid-a", enabled=False)
    assert service.get(job.job_id).state is JobState.READY_FOR_GENERATION
    assert all("cost" not in key for key in usage)


def test_generation_reservation_is_idempotent_and_enforces_caps():
    service, usage = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    assert service.authorize_generation(job.job_id, "uid-a", enabled=True)
    first_cost = usage["global-cost:2026-08-03"]
    assert not service.authorize_generation(job.job_id, "uid-a", enabled=True)
    assert usage["global-cost:2026-08-03"] == first_cost
    assert usage["user-generations:2026-08-03:uid-a"] == 1


def test_generation_quota_is_separate_from_free_validation_jobs():
    limits = replace(
        limits_for(Environment.DEVELOPMENT),
        daily_cost_cap_usd=10.0,
        user_daily_cost_cap_usd=10.0,
        generations_per_user_per_day=1,
    )
    service, usage = coordinator(limits=limits)
    first, _ = service.register("uid-a", "key-a", "original/a")
    second, _ = service.register("uid-a", "key-b", "original/b")

    assert service.authorize_generation(first.job_id, "uid-a", enabled=True)
    with pytest.raises(RateLimitExceeded):
        service.authorize_generation(second.job_id, "uid-a", enabled=True)

    assert usage["user-jobs:2026-08-03:uid-a"] == 2
    assert usage["user-generations:2026-08-03:uid-a"] == 1


def test_uid_job_quota_is_separate_from_generation_cost():
    limits = limits_for(Environment.DEVELOPMENT)
    service, usage = coordinator(limits=limits)
    for index in range(limits.jobs_per_user_per_day):
        service.register("uid-a", f"key-{index}", f"original/{index}")
    with pytest.raises(RateLimitExceeded):
        service.register("uid-a", "over", "original/over")
    assert all("cost" not in key for key in usage)


def test_global_cost_cap_blocks_before_mutating_usage():
    service, usage = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    usage["global-cost:2026-08-03"] = service.limits.daily_cost_cap_usd
    with pytest.raises(CostLimitExceeded):
        service.authorize_generation(job.job_id, "uid-a", enabled=True)
    assert usage["global-cost:2026-08-03"] == service.limits.daily_cost_cap_usd
    assert "user-cost:2026-08-03:uid-a" not in usage


def test_global_job_quota_blocks_many_anonymous_uids():
    limits = replace(limits_for(Environment.DEVELOPMENT), global_jobs_per_day=1)
    service, _ = coordinator(limits=limits)
    service.register("uid-a", "key-a", "original/a")
    with pytest.raises(RateLimitExceeded):
        service.register("uid-b", "key-b", "original/b")


def test_worker_success_cannot_overwrite_canceled_or_promote_files():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    assert service.authorize_generation(job.job_id, "uid-a", enabled=True)
    _, started = service.transition_if_active(job.job_id, JobState.VALIDATING_INPUT, JobState.GENERATING_MASTER)
    assert started
    service.cancel(job.job_id, "uid-a")
    promoted = []

    final, committed = service.commit_master_outputs(job.job_id, lambda _: promoted.append("master.png"))

    assert not committed
    assert final.state is JobState.CANCELED
    assert promoted == []


def test_worker_failure_cannot_overwrite_canceled():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    assert service.authorize_generation(job.job_id, "uid-a", enabled=True)
    service.transition_if_active(job.job_id, JobState.VALIDATING_INPUT, JobState.GENERATING_MASTER)
    service.cancel(job.job_id, "uid-a")

    final, changed = service.transition_if_active(
        job.job_id, JobState.GENERATING_MASTER, JobState.FAILED, "MASTER_GENERATION_FAILED"
    )

    assert not changed
    assert final.state is JobState.CANCELED


@pytest.mark.parametrize("terminal", [JobState.COMPLETED, JobState.FAILED, JobState.CANCELED])
def test_stale_worker_cannot_overwrite_any_terminal_state(terminal):
    service, _ = coordinator()
    job, _ = service.register("uid-a", "key-x", "original/hash")
    service.jobs[job.job_id]["state"] = terminal.value
    promoted = []

    final, committed = service.commit_master_outputs(job.job_id, lambda _: promoted.append("master.png"))
    failed, failure_written = service.transition_if_active(
        job.job_id, JobState.GENERATING_MASTER, JobState.FAILED, "MASTER_GENERATION_FAILED"
    )

    assert not committed and not failure_written
    assert final.state is terminal and failed.state is terminal
    assert promoted == []
