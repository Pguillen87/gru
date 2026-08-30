import json
from pathlib import Path

import pytest

from modal_service.model_cache import (
    ACTIVE_POINTER,
    ModelCacheNotReady,
    ModelCacheSpec,
    activate_cached_revision,
    prepare_model_cache,
    validate_active_cache,
)


SPEC = ModelCacheSpec(
    "qwen/model", "model-rev", "qwen/lora", "lora-rev", "adapter.safetensors"
)


def _prepare(root: Path, spec: ModelCacheSpec = SPEC):
    def snapshot_download(**_kwargs):
        snapshot = root / "hub" / "snapshots" / spec.model_revision
        (snapshot / "transformer").mkdir(parents=True, exist_ok=True)
        (snapshot / "transformer" / "weights.safetensors").write_bytes(b"model")
        (snapshot / "model_index.json").write_text("{}", encoding="utf-8")
        return str(snapshot)

    def hf_hub_download(**_kwargs):
        adapter = root / "hub" / "lora" / spec.lora_revision / spec.lora_weight
        adapter.parent.mkdir(parents=True, exist_ok=True)
        adapter.write_bytes(b"lora")
        return str(adapter)

    return prepare_model_cache(
        root,
        spec,
        snapshot_download=snapshot_download,
        hf_hub_download=hf_hub_download,
    )


def test_complete_cache_is_versioned_and_ready(tmp_path):
    cache = _prepare(tmp_path)

    assert cache.cache_revision == SPEC.cache_revision
    assert cache.expected_size == len(b"model{}lora")
    assert validate_active_cache(tmp_path, SPEC) == cache


def test_partial_cache_never_validates(tmp_path):
    cache = _prepare(tmp_path)
    (tmp_path / cache.expected_files[0].path).unlink()

    with pytest.raises(ModelCacheNotReady):
        validate_active_cache(tmp_path, SPEC)


def test_wrong_revision_never_validates(tmp_path):
    _prepare(tmp_path)
    other = ModelCacheSpec(
        "qwen/model", "other-rev", "qwen/lora", "lora-rev", "adapter.safetensors"
    )

    with pytest.raises(ModelCacheNotReady):
        validate_active_cache(tmp_path, other)


def test_invalid_manifest_never_validates(tmp_path):
    cache = _prepare(tmp_path)
    manifest_path = tmp_path / "manifests" / f"{cache.cache_revision}.json"
    manifest_path.write_text("not-json", encoding="utf-8")

    with pytest.raises(ModelCacheNotReady):
        validate_active_cache(tmp_path, SPEC)


def test_activation_keeps_previous_manifest_for_rollback(tmp_path):
    first = _prepare(tmp_path)
    second_spec = ModelCacheSpec(
        "qwen/model", "model-rev-2", "qwen/lora", "lora-rev", "adapter.safetensors"
    )
    second = _prepare(tmp_path, second_spec)

    activate_cached_revision(tmp_path, first.cache_revision)
    pointer = json.loads((tmp_path / ACTIVE_POINTER).read_text(encoding="utf-8"))

    assert pointer["cache_revision"] == first.cache_revision
    assert (tmp_path / "manifests" / f"{second.cache_revision}.json").is_file()
