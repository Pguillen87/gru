import hashlib
import json

import pytest
from PIL import Image

from modal_service.catalog import POSES, POSE_TEMPLATE_VERSION
from modal_service.templates import TemplatePackageError, validate_template_package


def test_complete_template_package_is_validated(tmp_path):
    poses = []
    for index, definition in enumerate(POSES, start=1):
        folder = tmp_path / definition.option_id
        folder.mkdir()
        reference = folder / "reference.png"
        Image.new("RGB", (256, 256), (index, 20, 30)).save(reference)
        poses.append({
            "role": definition.role,
            "option_id": definition.option_id,
            "template_id": definition.template_id,
            "name": definition.name,
            "version": POSE_TEMPLATE_VERSION,
            "reference": f"{definition.option_id}/reference.png",
            "instruction": definition.instruction,
            "sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        })
    manifest = {
        "version": POSE_TEMPLATE_VERSION,
        "catalog_version": POSE_TEMPLATE_VERSION,
        "poses": poses,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    package = validate_template_package(tmp_path)

    assert package.version == POSE_TEMPLATE_VERSION
    assert len(package.files) == 13


def test_template_package_rejects_path_escape(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({
        "version": "bad",
        "poses": [{"pose_id": f"pose_{i:02d}", "reference": "../outside.png"} for i in range(1, 7)],
        "consistency_pose_ids": ["pose_01", "pose_02", "pose_03"],
        "mvp_pose_ids": [f"pose_{i:02d}" for i in range(1, 7)],
    }), encoding="utf-8")

    with pytest.raises(TemplatePackageError):
        validate_template_package(tmp_path)


@pytest.mark.parametrize(
    ("version", "consistency", "mvp"),
    [
        ("../escape", ["pose_01", "pose_02", "pose_03"], [f"pose_{i:02d}" for i in range(1, 7)]),
        ("v1", ["pose_01", "pose_01", "pose_02"], [f"pose_{i:02d}" for i in range(1, 7)]),
        ("v1", ["pose_01", "pose_02", "pose_03"], ["pose_01"] * 6),
    ],
)
def test_template_package_rejects_unsafe_version_or_duplicate_sets(tmp_path, version, consistency, mvp):
    poses = []
    for index in range(1, 7):
        pose_id = f"pose_{index:02d}"
        folder = tmp_path / pose_id
        folder.mkdir()
        reference = folder / "reference.png"
        Image.new("RGB", (32, 32), (index, 20, 30)).save(reference)
        poses.append({
            "pose_id": pose_id,
            "name": f"pose {index}",
            "version": "v1",
            "difficulty": "simple",
            "reference": f"{pose_id}/reference.png",
            "instruction": "Preserve identity.",
            "sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        })
    (tmp_path / "manifest.json").write_text(json.dumps({
        "version": version,
        "poses": poses,
        "consistency_pose_ids": consistency,
        "mvp_pose_ids": mvp,
    }), encoding="utf-8")

    with pytest.raises(TemplatePackageError):
        validate_template_package(tmp_path)
