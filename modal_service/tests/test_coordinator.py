import pytest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from modal_service.config import Environment, limits_for
from modal_service.coordinator import JobCoordinator
from modal_service.costs import CostLimitExceeded, RateLimitExceeded
from modal_service.domain import DomainError, JobNotFound, JobState, WorkflowMode


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


def test_timeout_after_pose_call_id_is_reserved_never_reserves_a_second_gpu_call():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "key-timeout", "original/hash")
    service.jobs[job.job_id]["state"] = JobState.CONSISTENCY_TEST.value
    service.jobs[job.job_id]["master_id"] = "master_1"
    choices = {"normal": "normal_relaxed", "listening": "listening_ready", "transcribing": "transcribing_notes"}
    first, created, reserved = service.enqueue_pose_generation(job.job_id, "uid-a", choices, "op-timeout", "fp-timeout", "trace", "request")
    recorded, recorded_changed = service.record_pose_gpu_call(job.job_id, "fc-timeout")
    failed, failed_changed = service.fail_pose_generation(job.job_id, "POSE_WORKER_TIMEOUT")
    replay, replay_created, replay_reserved = service.enqueue_pose_generation(job.job_id, "uid-a", choices, "op-replay", "fp-timeout", "trace", "request-replay")

    assert created and reserved and recorded_changed and failed_changed
    assert first.pose_gpu_call_id == "reserved"
    assert recorded.pose_gpu_call_id == "fc-timeout"
    assert failed.state is JobState.FAILED
    assert not replay_created and not replay_reserved
    assert replay.pose_gpu_call_id == "fc-timeout"


def test_worker_crash_after_pose_gpu_start_never_enqueues_a_replacement():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "key-crash", "original/hash")
    service.jobs[job.job_id]["state"] = JobState.CONSISTENCY_TEST.value
    service.jobs[job.job_id]["master_id"] = "master_1"
    choices = {"normal": "normal_relaxed", "listening": "listening_ready", "transcribing": "transcribing_notes"}
    service.enqueue_pose_generation(job.job_id, "uid-a", choices, "op-crash", "fp-crash", "trace", "request")
    service.record_pose_gpu_call(job.job_id, "fc-crash")
    service.fail_pose_generation(job.job_id, "POSE_WORKER_CRASHED")
    replay, created, reserved = service.enqueue_pose_generation(job.job_id, "uid-a", choices, "op-replay", "fp-crash", "trace", "request-replay")

    assert replay.state is JobState.FAILED
    assert replay.pose_gpu_call_id == "fc-crash"
    assert not created and not reserved


def test_existing_pose_gpu_call_id_cannot_be_replaced():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "key-call-id", "original/hash")
    service.jobs[job.job_id]["state"] = JobState.CONSISTENCY_TEST.value
    service.jobs[job.job_id]["master_id"] = "master_1"
    choices = {"normal": "normal_relaxed", "listening": "listening_ready", "transcribing": "transcribing_notes"}
    service.enqueue_pose_generation(job.job_id, "uid-a", choices, "op-call-id", "fp-call-id", "trace", "request")
    first, first_changed = service.record_pose_gpu_call(job.job_id, "fc-first")
    second, second_changed = service.record_pose_gpu_call(job.job_id, "fc-second")

    assert first_changed and first.pose_gpu_call_id == "fc-first"
    assert not second_changed and second.pose_gpu_call_id == "fc-first"


def test_ambiguous_pose_response_without_outputs_never_restarts_gpu():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "key-ambiguous", "original/hash")
    service.jobs[job.job_id]["state"] = JobState.CONSISTENCY_TEST.value
    service.jobs[job.job_id]["master_id"] = "master_1"
    choices = {"normal": "normal_relaxed", "listening": "listening_ready", "transcribing": "transcribing_notes"}
    service.enqueue_pose_generation(job.job_id, "uid-a", choices, "op-ambiguous", "fp-ambiguous", "trace", "request")
    service.fail_pose_generation(job.job_id, "POSE_RESPONSE_AMBIGUOUS")
    replay, created, reserved = service.enqueue_pose_generation(job.job_id, "uid-a", choices, "op-replay", "fp-ambiguous", "trace", "request-replay")

    assert replay.state is JobState.FAILED
    assert replay.pose_gpu_call_id == "reserved"
    assert not created and not reserved


def test_async_incubation_replay_and_lease_are_serialized():
    service, usage = coordinator()
    args = {
        "registration_only": True,
        "attempt_id": "attempt-incubator",
        "workflow_mode": WorkflowMode.ASYNC_INCUBATOR_V1.value,
        "subject_hint": {"version": "subject-hint-v1", "suggestedCategory": "animal"},
    }
    first, created = service.register("uid-a", "incubator-key", "original/hash", **args)
    replay, replay_created = service.register("uid-a", "incubator-key", "original/hash", **args)

    assert created and not replay_created and first.job_id == replay.job_id
    assert usage["user-jobs:2026-08-03:uid-a"] == 1

    service.jobs[first.job_id]["state"] = JobState.AWAITING_MASTER_APPROVAL.value
    claimed, changed = service.claim_incubation_lease(first.job_id, "worker-a", 60)
    concurrent, concurrent_changed = service.claim_incubation_lease(first.job_id, "worker-b", 60)
    assert changed and claimed.lease_owner == "worker-a"
    assert not concurrent_changed and concurrent.lease_owner == "worker-a"

    released, release_changed = service.release_incubation_lease(first.job_id, "worker-a")
    assert release_changed and released.lease_owner is None


def test_shadow_ranking_persists_versions_without_selecting_a_master_or_pose_operation():
    service, _ = coordinator()
    job, _ = service.register(
        "uid-a", "incubator-shadow", "original/hash", registration_only=True,
        workflow_mode=WorkflowMode.ASYNC_INCUBATOR_V1.value,
        subject_hint={"version": "subject-hint-policy-v2", "suggestedCategory": "uncertain"},
    )
    service.jobs[job.job_id]["state"] = JobState.AWAITING_MASTER_APPROVAL.value
    observation = {
        "encoderVersion": "siglip-base-p16-224-zeroshot-v1",
        "masterRankerVersion": "master-ranker-v2",
        "candidateCount": 3,
        "winner": "master_2",
        "highestScore": 0.91,
    }
    recorded, changed = service.record_shadow_ranking(job.job_id, observation)
    replay, replay_changed = service.record_shadow_ranking(job.job_id, observation)

    assert changed and not replay_changed
    assert recorded.master_id is None and recorded.master_selection is None
    assert recorded.pose_gpu_call_id is None and recorded.pose_operation_id is None
    assert recorded.encoder_version == observation["encoderVersion"]
    assert recorded.master_ranker_version == observation["masterRankerVersion"]
    assert recorded.subject_hint_policy_version == "subject-hint-policy-v2"
    assert replay.shadow_ranking_observation == observation


def test_async_incubation_heartbeat_requires_the_current_lease_owner():
    service, _ = coordinator()
    job, _ = service.register(
        "uid-a",
        "incubator-heartbeat",
        "original/hash",
        registration_only=True,
        attempt_id="attempt-incubator",
        workflow_mode=WorkflowMode.ASYNC_INCUBATOR_V1.value,
    )
    service.jobs[job.job_id]["state"] = JobState.AWAITING_MASTER_APPROVAL.value
    service.claim_incubation_lease(job.job_id, "worker-a", 60)

    rejected, rejected_changed = service.heartbeat_incubation(job.job_id, "worker-b", 60)
    renewed, renewed_changed = service.heartbeat_incubation(job.job_id, "worker-a", 60)

    assert not rejected_changed and rejected.lease_owner == "worker-a"
    assert renewed_changed and renewed.lease_owner == "worker-a"
    assert renewed.heartbeat_at and renewed.lease_expires_at


def test_async_incubation_restart_recovers_only_an_expired_lease():
    service, _ = coordinator()
    job, _ = service.register(
        "uid-a",
        "incubator-restart",
        "original/hash",
        registration_only=True,
        attempt_id="attempt-incubator",
        workflow_mode=WorkflowMode.ASYNC_INCUBATOR_V1.value,
    )
    service.jobs[job.job_id]["state"] = JobState.AWAITING_MASTER_APPROVAL.value
    service.claim_incubation_lease(job.job_id, "worker-before-restart", 60)
    service.jobs[job.job_id]["lease_expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()

    recovered, changed = service.claim_incubation_lease(job.job_id, "worker-after-restart", 60)

    assert changed and recovered.lease_owner == "worker-after-restart"


def test_async_master_selection_and_generation_ready_are_idempotent():
    service, _ = coordinator()
    job, _ = service.register(
        "uid-a",
        "incubator-key",
        "original/hash",
        registration_only=True,
        attempt_id="attempt-incubator",
        workflow_mode=WorkflowMode.ASYNC_INCUBATOR_V1.value,
    )
    service.jobs[job.job_id]["state"] = JobState.AWAITING_MASTER_APPROVAL.value
    selection = {"rankerVersion": "master-ranker-v1", "selectedMasterId": "master_1", "scores": [], "decision": "AUTO_SELECTED", "selectionSource": "auto"}
    selected, changed = service.auto_select_master(job.job_id, selection, "pose-prompt")
    replay, replay_changed = service.auto_select_master(job.job_id, selection, "pose-prompt")
    assert changed and not replay_changed and selected.master_id == replay.master_id == "master_1"

    service.start_pose_generation(job.job_id, selected.pose_choices)
    completed, committed = service.commit_pose_outputs(job.job_id, lambda _: None)
    repeated, repeated_commit = service.commit_pose_outputs(job.job_id, lambda _: None)
    assert committed and not repeated_commit
    assert completed.generation_ready_at and repeated.generation_ready_at == completed.generation_ready_at


def test_ambiguous_incubator_requires_owner_selection_and_replays_idempotently():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "ambiguous-key", "original/hash", registration_only=True, attempt_id="attempt-ambiguous", workflow_mode=WorkflowMode.ASYNC_INCUBATOR_V1.value)
    service.jobs[job.job_id]["state"] = JobState.AWAITING_MASTER_APPROVAL.value
    service.record_shadow_ranking(job.job_id, {"decision": "NEEDS_HUMAN_SELECTION", "selectedMasterId": "master_2", "scores": []})
    selected, changed = service.select_incubator_master(job.job_id, "uid-a", "master_3", "pose-prompt")
    replay, replay_changed = service.select_incubator_master(job.job_id, "uid-a", "master_3", "pose-prompt")
    assert changed and not replay_changed
    assert selected.master_id == replay.master_id == "master_3"
    assert selected.master_selection["selectionSource"] == "human"


def test_ranking_failure_is_persisted_without_selecting_a_master():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "rank-fail", "original/hash", registration_only=True, attempt_id="attempt-rank-fail", workflow_mode=WorkflowMode.ASYNC_INCUBATOR_V1.value)
    service.jobs[job.job_id]["state"] = JobState.AWAITING_MASTER_APPROVAL.value
    failed, _ = service.fail_incubation(job.job_id, "MASTER_AUTO_RANKING_FAILED")
    assert failed.master_id is None
    assert failed.master_selection["decision"] == "RANKING_FAILED"


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


def test_preserved_raw_recovery_is_owner_scoped_idempotent_and_never_reserves_gpu():
    service, _ = coordinator()
    job, _ = service.register("uid-a", "recovery-key", "original/hash", workflow_mode=WorkflowMode.ASYNC_INCUBATOR_V1.value)
    record = service.get(job.job_id)
    record.state = JobState.FAILED
    record.error_code = "VISUAL_POSE_CONSISTENCY_FAILED"
    record.master_id = "master_2"
    record.pose_operation_id = "incubator_pose_1"
    record.pose_operation_status = "failed"
    record.pose_gpu_call_id = "fc-existing"
    service.save(record)
    persisted: list[str] = []

    recovered, changed = service.recover_pose_outputs_from_preserved_raws(
        job.job_id, "uid-a", lambda current: persisted.append(current.pose_gpu_call_id or ""), "pose-set-visual-v3"
    )
    replay, replay_changed = service.recover_pose_outputs_from_preserved_raws(
        job.job_id, "uid-a", lambda current: persisted.append("unexpected"), "pose-set-visual-v3"
    )

    assert changed and not replay_changed
    assert recovered.state is JobState.COMPLETED
    assert recovered.pose_gpu_call_id == "fc-existing"
    assert recovered.pose_operation_id == "incubator_pose_1"
    assert recovered.master_id == "master_2"
    assert recovered.pose_recovery["recoveredFromErrorCode"] == "VISUAL_POSE_CONSISTENCY_FAILED"
    assert replay.generation_ready_at
    assert persisted == ["fc-existing"]


@pytest.mark.parametrize("error_code", ["POSE_ALPHA_QC_FAILED", "POSE_GENERATION_FAILED"])
def test_preserved_raw_recovery_fails_closed_for_an_incompatible_failure(error_code):
    service, _ = coordinator()
    job, _ = service.register("uid-a", "recovery-incompatible", "original/hash")
    record = service.get(job.job_id)
    record.state = JobState.FAILED
    record.error_code = error_code
    record.master_id = "master_2"
    record.pose_operation_id = "incubator_pose_1"
    record.pose_operation_status = "failed"
    record.pose_gpu_call_id = "fc-existing"
    service.save(record)

    with pytest.raises(DomainError, match="not compatible"):
        service.recover_pose_outputs_from_preserved_raws(
            job.job_id, "uid-a", lambda current: (_ for _ in ()).throw(AssertionError("must not persist")), "pose-set-visual-v3"
        )


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
