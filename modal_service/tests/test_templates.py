import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from modal_service import app
from modal_service.catalog import POSE_REFERENCES, POSE_TEMPLATE_VERSION
from modal_service.templates import TemplatePackageError, validate_active_template_package, validate_template_package
from modal_service.tools.install_pose_templates import PRODUCTION_RESOURCE_PREFIX, validate_install_target


def _write_package(root, *, mutate=None):
    poses = []
    for index, reference in enumerate(POSE_REFERENCES):
        folder = root / reference.option_id
        folder.mkdir(parents=True)
        image_path = folder / "reference.png"
        Image.new("RGB", (256, 256), (20 + index, 40, 60)).save(image_path)
        poses.append(
            {
                "option_id": reference.option_id,
                "role": reference.role,
                "label": reference.label,
                "instruction": reference.instruction,
                "reference": f"{reference.option_id}/reference.png",
                "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            }
        )
    manifest = {
        "version": POSE_TEMPLATE_VERSION,
        "catalog_version": POSE_TEMPLATE_VERSION,
        "asset_provenance": {
            "source_type": "test",
            "repository": "Pguillen87/PuleiroGru",
            "commit": "test",
            "source_path": "public/assets/pose-reference-sheet.webp",
            "rights_basis": "test fixture",
        },
        "poses": poses,
    }
    if mutate:
        mutate(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_complete_web_pose_package_is_validated(tmp_path):
    _write_package(tmp_path)

    package = validate_template_package(tmp_path)

    assert package.version == POSE_TEMPLATE_VERSION
    assert len(package.files) == len(POSE_REFERENCES) + 1
    assert package.reference_for("normal_attentive").is_file()


def test_template_package_rejects_catalog_mismatch(tmp_path):
    _write_package(tmp_path, mutate=lambda manifest: manifest["poses"].pop())

    with pytest.raises(TemplatePackageError):
        validate_template_package(tmp_path)


def test_template_package_rejects_incompatible_pose_metadata(tmp_path):
    _write_package(tmp_path, mutate=lambda manifest: manifest["poses"][0].__setitem__("role", "listening"))

    with pytest.raises(TemplatePackageError):
        validate_template_package(tmp_path)


def test_active_pointer_requires_a_valid_package(monkeypatch, tmp_path):
    package_root = tmp_path / "pose_templates" / "versions" / POSE_TEMPLATE_VERSION
    _write_package(package_root)
    active = tmp_path / "pose_templates" / "active.json"
    active.parent.mkdir(parents=True, exist_ok=True)
    active.write_text(json.dumps({"version": POSE_TEMPLATE_VERSION}), encoding="utf-8")

    assert validate_active_template_package(tmp_path).version == POSE_TEMPLATE_VERSION
    monkeypatch.setattr(app, "ASSET_ROOT", str(tmp_path))
    assert app._templates_installed() is True
    assert app._active_pose_template_version() == POSE_TEMPLATE_VERSION


def test_repository_package_matches_the_published_web_catalog_and_records_origin():
    package = validate_template_package(
        Path(__file__).parents[1] / "pose_templates" / POSE_TEMPLATE_VERSION
    )

    provenance = package.manifest["asset_provenance"]
    assert provenance["repository"] == "Pguillen87/PuleiroGru"
    assert provenance["source_path"] == "public/assets/pose-reference-sheet.webp"
    assert len(package.manifest["poses"]) == 12


def test_production_template_install_requires_the_exact_explicit_target():
    with pytest.raises(SystemExit):
        validate_install_target(resource_prefix=PRODUCTION_RESOURCE_PREFIX, environment="main", allow_production=False)
    with pytest.raises(SystemExit):
        validate_install_target(resource_prefix="gru-mascot-v2-staging", environment="main", allow_production=True)

    validate_install_target(resource_prefix=PRODUCTION_RESOURCE_PREFIX, environment="main", allow_production=True)


def test_non_production_template_install_rejects_the_production_override():
    validate_install_target(resource_prefix="gru-mascot-v2-staging", environment="staging", allow_production=False)
    with pytest.raises(SystemExit):
        validate_install_target(resource_prefix="gru-mascot-v2-staging", environment="staging", allow_production=True)
