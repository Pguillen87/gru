import pytest

from modal_service.catalog import (
    MASTER_PROMPT,
    MASTER_PROMPT_VERSION,
    POSE_PROMPT,
    validate_pose_choices,
)
from modal_service.domain import JobRecord


def test_master_prompt_preserves_human_or_animal_subject_without_hybrid_features():
    prompt = MASTER_PROMPT.lower()

    assert MASTER_PROMPT_VERSION == "master-v3-identity"
    assert "human remains a human" in prompt
    assert "exact species" in prompt
    assert "never add animal ears" in prompt
    assert "identity evidence" in prompt
    assert "do not copy the source pose" in prompt


def test_pose_prompt_keeps_a_human_human():
    prompt = POSE_PROMPT.lower()

    assert "subject category" in prompt
    assert "no animal ears" in prompt


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
