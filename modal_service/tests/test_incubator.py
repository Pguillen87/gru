from dataclasses import replace

import pytest

from modal_service.domain import JobRecord, JobState, WorkflowMode
from modal_service.incubator import (
    NeutralVisualEncoder,
    VisualEncoderUnavailable,
    load_pinned_visual_encoder,
    pinned_encoder_status,
    product_state,
    rank_masters,
    shadow_ranking_observation,
    subject_hint,
)


class FakeEncoder:
    version = "fake-v1"

    def encode(self, image: bytes) -> tuple[float, ...]:
        return {
            b"source": (1.0, 0.0),
            b"one": (0.98, 0.02),
            b"two": (0.80, 0.20),
            b"three": (0.70, 0.30),
        }[image]

    def classify(self, image: bytes) -> dict[str, float]:
        del image
        return {"human": 0.92, "animal": 0.04, "object": 0.02, "other": 0.02}

    def provenance(self) -> dict[str, str]:
        return {"encoderVersion": self.version}


def passed_qc() -> dict[str, object]:
    return {"status": "passed", "alpha_ratio": 0.55, "border_opaque_ratio": 0.01, "component_count": 1}


def test_subject_hint_warns_only_for_a_high_confidence_mismatch():
    hint = subject_hint("human", {"human": 0.04, "animal": 0.93})
    assert hint == {
        "version": "subject-hint-policy-v2",
        "suggestedCategory": "animal",
        "confidenceBand": "high",
        "requiresConfirmation": True,
        "overrideConfirmed": False,
    }


def test_subject_hint_is_non_blocking_when_scores_are_uncertain():
    hint = subject_hint("human", {"human": 0.55, "animal": 0.45})
    assert hint["suggestedCategory"] == "uncertain"
    assert hint["requiresConfirmation"] is False


def test_unavailable_subject_hint_preserves_the_explicit_human_choice():
    hint = subject_hint("animal", NeutralVisualEncoder().classify(b"not-used"))
    assert hint["suggestedCategory"] == "uncertain"
    assert hint["requiresConfirmation"] is False


def test_pinned_encoder_fails_closed_when_no_verified_artifact_is_configured(monkeypatch):
    monkeypatch.delenv("INCUBATOR_VISUAL_ENCODER_DIR", raising=False)
    with pytest.raises(VisualEncoderUnavailable, match="NOT_CONFIGURED"):
        load_pinned_visual_encoder()
    assert pinned_encoder_status()["ready"] is False


def test_master_ranking_requires_three_candidates_and_is_deterministic():
    selection = rank_masters(
        b"source",
        {"master_1": b"one", "master_2": b"two", "master_3": b"three"},
        {master_id: passed_qc() for master_id in ("master_1", "master_2", "master_3")},
        "human",
        FakeEncoder(),
    )
    assert selection["selectedMasterId"] == "master_1"
    assert [item["masterId"] for item in selection["scores"]] == ["master_1", "master_2", "master_3"]
    assert selection["encoderVersion"] == "fake-v1"
    assert selection["masterRankerVersion"] == "master-ranker-v2"

    with pytest.raises(ValueError, match="exactly three"):
        rank_masters(b"source", {"master_1": b"one"}, {"master_1": passed_qc()}, "human", FakeEncoder())


def test_master_ranking_fails_when_every_candidate_fails_hard_qc():
    with pytest.raises(ValueError, match="No Master"):
        rank_masters(
            b"source",
            {"master_1": b"one", "master_2": b"two", "master_3": b"three"},
            {master_id: {"status": "failed"} for master_id in ("master_1", "master_2", "master_3")},
            "human",
            FakeEncoder(),
        )


def test_shadow_ranking_observation_excludes_embeddings_and_is_not_a_selection_state():
    selection = rank_masters(
        b"source",
        {"master_1": b"one", "master_2": b"two", "master_3": b"three"},
        {master_id: passed_qc() for master_id in ("master_1", "master_2", "master_3")},
        "human",
        FakeEncoder(),
    )
    observation = shadow_ranking_observation(selection)
    assert observation["winner"] == "master_1"
    assert observation["candidateCount"] == 3
    assert "embedding" not in repr(observation).lower()
    assert set(observation) == {"encoderVersion", "masterRankerVersion", "candidateCount", "winner", "highestScore"}


def test_product_state_is_derived_instead_of_persisted_separately():
    base = JobRecord("job", "owner", "key", "source", workflow_mode=WorkflowMode.ASYNC_INCUBATOR_V1.value)
    assert product_state(replace(base, state=JobState.REGISTERED)) == "PREPARING"
    assert product_state(replace(base, state=JobState.GENERATING_MASTER)) == "INCUBATING"
    assert product_state(replace(base, state=JobState.COMPLETED, generation_ready_at="2026-08-29T00:00:00+00:00")) == "READY_TO_HATCH"
    assert product_state(replace(base, state=JobState.FAILED)) == "FAILED"
