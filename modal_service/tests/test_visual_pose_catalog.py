from io import BytesIO
import json

import pytest
from PIL import Image, ImageDraw

from modal_service import app
from modal_service.catalog import DEFAULT_POSE_CHOICES, POSE_OPTIONS
from modal_service.domain import DomainError, JobRecord, PoseAlphaQualityError, PoseVisualConsistencyError


class _Volume:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def _generated_pose(background=(242, 235, 219), *, opaque=False) -> bytes:
    image = Image.new("RGBA", (96, 96), (*background, 255))
    drawer = ImageDraw.Draw(image)
    drawer.ellipse((32, 14, 64, 50), fill=(52, 80, 120, 255))
    drawer.rectangle((37, 45, 59, 82), fill=(52, 80, 120, 255))
    if opaque:
        image = image.convert("RGB")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _unrecoverable_pose() -> bytes:
    image = Image.new("RGB", (96, 96), (52, 80, 120))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _job() -> JobRecord:
    return JobRecord("job-1", "user", "key", "source", master_id="master_1")


def _outputs():
    selected = [option for option in POSE_OPTIONS if option.option_id in DEFAULT_POSE_CHOICES.values()]
    return {option.option_id: _generated_pose() for option in selected}


def test_pose_persistence_promotes_exactly_three_rgba_derivatives_and_preserves_raw(monkeypatch, tmp_path):
    volume = _Volume()
    monkeypatch.setattr(app, "ASSET_ROOT", str(tmp_path))
    monkeypatch.setattr(app, "assets", volume)
    job = _job()

    app._persist_pose_outputs(job, _outputs())

    result_root = tmp_path / "poses" / job.job_id
    raw_root = tmp_path / "poses_raw" / job.job_id
    manifest = json.loads((result_root / "manifest.json").read_text(encoding="utf-8"))
    qc = json.loads((result_root / "qc.json").read_text(encoding="utf-8"))["poses"]
    assert len(manifest["poses"]) == 3
    assert {pose["runtimeRole"] for pose in manifest["poses"]} == {"normal", "listening", "transcribing"}
    assert {pose["optionId"] for pose in manifest["poses"]} == set(_outputs())
    assert manifest["poseSetQc"]["status"] == "passed"
    assert set(qc) == {"pose_01", "pose_02", "pose_03"}
    assert all(item["status"] == "passed" for item in qc.values())
    assert all((raw_root / f"{option_id}.png").is_file() for option_id in _outputs())
    assert all((result_root / f"pose_{index:02d}.png").is_file() for index in range(1, 4))
    assert not (result_root / "pose_04.png").exists()
    app._verify_pose_outputs(job)
    assert volume.commits == 1


def test_pose_visual_consistency_failure_preserves_the_previous_promoted_set(monkeypatch, tmp_path):
    volume = _Volume()
    monkeypatch.setattr(app, "ASSET_ROOT", str(tmp_path))
    monkeypatch.setattr(app, "assets", volume)
    job = _job()
    existing = tmp_path / "poses" / job.job_id
    existing.mkdir(parents=True)
    (existing / "preserved.txt").write_text("prior set", encoding="utf-8")
    outputs = _outputs()
    outputs[next(iter(outputs))] = _generated_pose()

    # Simulate an obviously zoomed/cropped source only in this free test.
    from modal_service import image_processing
    original_qc = image_processing.pose_transparency_qc
    calls = 0
    def inconsistent_qc(content):
        nonlocal calls
        calls += 1
        result = original_qc(content)
        if calls == 2:
            return result | {"width": 640, "height": 640, "bounding_box": [0, 10, 640, 630]}
        return result
    monkeypatch.setattr(image_processing, "pose_transparency_qc", inconsistent_qc)

    with pytest.raises(PoseVisualConsistencyError, match="visual consistency") as error:
        app._persist_pose_outputs(job, outputs)

    assert error.value.code == "VISUAL_POSE_CONSISTENCY_FAILED"
    assert (existing / "preserved.txt").read_text(encoding="utf-8") == "prior set"
    assert not (existing / "pose_01.png").exists()


def test_pose_qc_failure_keeps_previous_set_and_does_not_promote_a_partial_result(monkeypatch, tmp_path):
    volume = _Volume()
    monkeypatch.setattr(app, "ASSET_ROOT", str(tmp_path))
    monkeypatch.setattr(app, "assets", volume)
    job = _job()
    existing = tmp_path / "poses" / job.job_id
    existing.mkdir(parents=True)
    (existing / "preserved.txt").write_text("prior set", encoding="utf-8")
    outputs = _outputs()
    outputs[next(iter(outputs))] = _unrecoverable_pose()

    with pytest.raises(PoseAlphaQualityError, match="alpha quality") as error:
        app._persist_pose_outputs(job, outputs)

    assert error.value.code == "POSE_ALPHA_QC_FAILED"
    assert (existing / "preserved.txt").read_text(encoding="utf-8") == "prior set"
    assert not (existing / "pose_01.png").exists()
    assert all((tmp_path / "poses_raw" / job.job_id / f"{option_id}.png").is_file() for option_id in outputs)
    assert volume.commits == 1


def test_raw_pose_recovery_requires_exactly_the_three_reserved_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "ASSET_ROOT", str(tmp_path))
    job = _job()
    raw_root = tmp_path / "poses_raw" / job.job_id
    raw_root.mkdir(parents=True)
    for option_id, output in _outputs().items():
        (raw_root / f"{option_id}.png").write_bytes(output)

    recovered = app._load_raw_pose_outputs(job)

    assert set(recovered) == set(_outputs())
    (raw_root / "unexpected.png").write_bytes(_generated_pose())
    with pytest.raises(DomainError, match="exactly the reserved three"):
        app._load_raw_pose_outputs(job)
