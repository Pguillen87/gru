from modal_service.catalog import MASTER_PROMPT_VERSION, POSE_CATALOG, build_master_prompt, build_pose_prompt
from modal_service.domain import JobRecord


def test_master_prompt_preserves_human_or_animal_subject_without_hybrid_features():
    prompt = build_master_prompt({"category": "human", "label": "Pessoa", "confirmed": True}).lower()

    assert MASTER_PROMPT_VERSION == "master-v4"
    assert "subject is human" in prompt
    assert "never add fur" in prompt
    assert "do not invent tattoos" in prompt
    assert "unseen areas" in prompt


def test_pose_prompt_keeps_a_human_human():
    prompt = build_pose_prompt({"category": "human", "confirmed": True}, "Listen attentively.").lower()

    assert "approved gru master" in prompt
    assert "ordinary human ears" in prompt
    assert "no ground shadow" in prompt


def test_web_catalog_has_exactly_four_options_per_role():
    assert {role: len(options) for role, options in POSE_CATALOG.items()} == {
        "normal": 4, "listening": 4, "transcribing": 4,
    }


def test_new_jobs_record_the_current_master_prompt_version():
    assert JobRecord("job", "user", "key", "source").prompt_version == MASTER_PROMPT_VERSION
