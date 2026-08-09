import json

from modal_service import app
from modal_service.catalog import DEFAULT_POSE_CHOICES, POSE_OPTIONS
from modal_service.domain import JobRecord


class _Volume:
    def commit(self):
        pass


def test_pose_persistence_exposes_twelve_selectable_images(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "ASSET_ROOT", str(tmp_path))
    monkeypatch.setattr(app, "assets", _Volume())
    monkeypatch.setattr("modal_service.image_processing.remove_connected_flat_background", lambda value: value)
    job = JobRecord("job-1", "user", "key", "source", master_id="master_1")
    outputs = {option.option_id: f"image-{option.option_id}".encode() for option in POSE_OPTIONS}

    app._persist_pose_outputs(job, outputs)

    manifest = json.loads((tmp_path / "poses" / "job-1" / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["poses"]) == 12
    assert {pose["runtimeRole"] for pose in manifest["poses"]} == {"normal", "listening", "transcribing"}
    assert {pose["optionId"] for pose in manifest["poses"]} == set(outputs)
    by_option = {pose["optionId"]: pose["poseId"] for pose in manifest["poses"]}
    assert manifest["idlePoseId"] == by_option[DEFAULT_POSE_CHOICES["normal"]]
    assert manifest["listeningPoseId"] == by_option[DEFAULT_POSE_CHOICES["listening"]]
    assert manifest["transcribingPoseId"] == by_option[DEFAULT_POSE_CHOICES["transcribing"]]
