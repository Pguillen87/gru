import inspect
import json
import sys
import types

from PIL import Image

from modal_service import app
from modal_service.app import _generate_qwen_masters, _generate_qwen_poses, _load_qwen_pipeline
from modal_service.catalog import DEFAULT_POSE_CHOICES, POSE_TEMPLATE_VERSION
from modal_service.domain import JobRecord
from modal_service.inference_observability import InferenceObserver


def test_user_generation_never_downloads_or_rebuilds_the_pipeline():
    generation_source = inspect.getsource(_generate_qwen_masters)
    loader_source = inspect.getsource(_load_qwen_pipeline)

    assert "from_pretrained" not in generation_source
    assert "load_lora_weights" not in generation_source
    assert "huggingface_hub" not in generation_source
    assert "huggingface_hub" not in loader_source
    assert "local_files_only=True" in loader_source

    pose_source = inspect.getsource(_generate_qwen_poses)
    assert "from_pretrained" not in pose_source
    assert "load_lora_weights" not in pose_source
    assert 'for role in ("normal", "listening", "transcribing")' in pose_source
    assert "pose_option(job.pose_choices[role])" in pose_source
    assert "_active_pose_template(option.option_id)" in pose_source
    assert "image=[master, pose_reference]" in pose_source
    assert "option_seeds" in pose_source


def test_fake_pose_worker_receives_master_and_template_for_exactly_three_outputs(monkeypatch, tmp_path):
    assets = tmp_path
    master_path = assets / "masters" / "job-1"
    master_path.mkdir(parents=True)
    Image.new("RGBA", (300, 300), (30, 50, 90, 0)).save(master_path / "master_1.png")
    template_root = assets / "pose_templates" / "versions" / POSE_TEMPLATE_VERSION
    poses = []
    from modal_service.catalog import POSE_REFERENCES
    import hashlib
    for index, reference in enumerate(POSE_REFERENCES):
        path = template_root / reference.option_id / "reference.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (256, 256), (20 + index, 40, 60)).save(path)
        poses.append({
            "option_id": reference.option_id,
            "role": reference.role,
            "label": reference.label,
            "instruction": reference.instruction,
            "reference": f"{reference.option_id}/reference.png",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    (template_root / "manifest.json").write_text(json.dumps({
        "version": POSE_TEMPLATE_VERSION,
        "catalog_version": POSE_TEMPLATE_VERSION,
        "asset_provenance": {"source_type": "test", "repository": "test", "commit": "test", "source_path": "test", "rights_basis": "test"},
        "poses": poses,
    }), encoding="utf-8")
    active = assets / "pose_templates" / "active.json"
    active.parent.mkdir(parents=True, exist_ok=True)
    active.write_text(json.dumps({"version": POSE_TEMPLATE_VERSION}), encoding="utf-8")
    monkeypatch.setattr(app, "ASSET_ROOT", str(assets))

    class FakeGenerator:
        def __init__(self, _device):
            pass

        def manual_seed(self, _seed):
            return self

    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(Generator=FakeGenerator))
    calls = []

    class FakePipeline:
        def __call__(self, **kwargs):
            calls.append(kwargs)
            return types.SimpleNamespace(images=[Image.new("RGB", (300, 300), (100, 120, 140))])

    job = JobRecord("job-1", "uid", "key", "source", master_id="master_1", pose_choices=dict(DEFAULT_POSE_CHOICES))
    output = _generate_qwen_poses(job, FakePipeline(), InferenceObserver("test"))

    assert set(output) == set(DEFAULT_POSE_CHOICES.values())
    assert len(calls) == 3
    assert all(len(call["image"]) == 2 for call in calls)
    assert all(call["image"][0].mode == "RGB" and call["image"][1].mode == "RGB" for call in calls)
