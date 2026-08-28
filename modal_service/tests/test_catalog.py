import pytest

from modal_service.catalog import (
    MASTER_PROMPT_VERSION,
    POSE_OPTIONS,
    build_master_negative_prompt,
    build_pose_negative_prompt,
    build_master_prompt,
    build_pose_prompt,
    pose_option,
    validate_pose_choices,
)
from modal_service.app import POSE_TRUE_CFG_SCALE
from modal_service.domain import JobRecord


def test_human_prompt_keeps_clothing_patterns_off_skin_and_blocks_hybrid_features():
    identity = {"category": "human", "label": "bald bearded person", "species": None}
    prompt = build_master_prompt(identity).lower()
    negative = build_master_negative_prompt(identity).lower()

    assert MASTER_PROMPT_VERSION == "master-v4-confirmed-category"
    assert "anatomically human" in prompt
    assert "clothing colors and prints must remain on clothing only" in prompt
    assert "animal ears" in negative and "clothing pattern on skin" in negative
    assert "preserve the confirmed category exactly" in prompt


def test_pose_prompt_keeps_a_human_human_and_uses_only_the_master():
    prompt = build_pose_prompt(
        {"category": "human", "label": "person", "species": None},
        "listening",
        pose_option("listening_focus"),
    ).lower()

    assert "subject category" in prompt
    assert "no animal ears" in prompt
    assert "only the approved master" in prompt
    assert "full body visible from head to both feet" in prompt
    assert "never make a bust, close-up" in prompt


def test_transcribing_prompt_requires_a_standing_full_body_with_only_a_small_prop():
    identity = {"category": "human", "label": "person", "species": None}
    prompt = build_pose_prompt(identity, "transcribing", pose_option("transcribing_active")).lower()
    negative = build_pose_negative_prompt(identity, "transcribing").lower()

    assert "keep the character standing and fully visible from head to both feet" in prompt
    assert "small handheld notepad" in prompt
    assert "do not add a desk, chair, table, workstation" in prompt
    assert "seated, sitting, chair, desk, table" in negative


def test_pose_negative_prompt_is_backed_by_enabled_true_cfg():
    assert POSE_TRUE_CFG_SCALE > 1.0


def test_normal_and_listening_keep_their_existing_role_scope():
    identity = {"category": "human", "label": "person", "species": None}
    normal = build_pose_prompt(identity, "normal", pose_option("normal_attentive")).lower()
    listening = build_pose_prompt(identity, "listening", pose_option("listening_focus")).lower()

    assert "small handheld notepad" not in normal
    assert "small handheld notepad" not in listening


def test_new_jobs_record_the_current_master_prompt_version():
    assert JobRecord("job", "user", "key", "source").prompt_version == MASTER_PROMPT_VERSION


def test_pose_choices_require_one_valid_option_per_runtime_role():
    choices = {
        "normal": "normal_curious",
        "listening": "listening_natural",
        "transcribing": "transcribing_notes",
    }

    assert validate_pose_choices(choices) == choices
    with pytest.raises(ValueError):
        validate_pose_choices(choices | {"normal": "listening_focus"})


def test_visual_catalog_has_four_approved_options_for_each_runtime_role():
    labels = {
        role: [option.label for option in POSE_OPTIONS if option.role == role]
        for role in ("normal", "listening", "transcribing")
    }

    assert labels == {
        "normal": ["Pronto e atento", "Relaxado", "Observador", "Espera paciente"],
        "listening": ["Gesto de escuta", "Inclinado para ouvir", "Reação natural", "Cabeça inclinada"],
        "transcribing": ["Escrevendo", "Digitando", "Organizando ideias", "Anotando"],
    }
