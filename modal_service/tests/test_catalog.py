import pytest

from modal_service.catalog import (
    MASTER_PROMPT_VERSION,
    POSE_OPTIONS,
    build_master_negative_prompt,
    build_master_prompt,
    build_pose_prompt,
    pose_option,
    validate_pose_choices,
)
from modal_service.domain import JobRecord


def test_human_prompt_keeps_clothing_patterns_off_skin_and_blocks_hybrid_features():
    identity = {"category": "human", "label": "bald bearded person", "species": None}
    prompt = build_master_prompt(identity).lower()
    negative = build_master_negative_prompt(identity).lower()

    assert MASTER_PROMPT_VERSION == "master-v5-object-integrity"
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


def test_object_prompt_keeps_the_object_without_inventing_a_humanoid_body():
    identity = {"category": "object", "label": "red push button", "species": None}
    prompt = build_master_prompt(identity).lower()
    negative = build_master_negative_prompt(identity).lower()

    assert "complete object itself" in prompt
    assert "do not add torso, arms, legs, hands, feet" in prompt
    assert "robot body" in negative
    assert "full-body" not in prompt


def test_object_pose_prompt_uses_object_specific_actions_without_humanoid_anatomy():
    prompt = build_pose_prompt(
        {"category": "object", "label": "red push button", "species": None},
        "transcribing",
        pose_option("transcribing_fast"),
    ).lower()

    assert "integrated on the object itself" in prompt
    assert "do not add a keyboard, pencil, notes, hands" in prompt


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
