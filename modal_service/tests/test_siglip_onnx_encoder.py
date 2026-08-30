from __future__ import annotations

import hashlib
import json
import sys
import types
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from modal_service.incubator import (
    ARTIFACT_PACKAGE_NAME,
    SiglipOnnxVisualEncoder,
    UPSTREAM_WEIGHTS_SHA256,
    VisualEncoderUnavailable,
    prompt_contract_sha256,
)


PROMPTS = ["a photo of a person", "a photo of an animal", "a photo of an object", "a photo of scenery"]
CATEGORIES = [0, 1, 2, 3]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(package: Path) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "artifact": {"package": ARTIFACT_PACKAGE_NAME, "encoderVersion": ARTIFACT_PACKAGE_NAME},
        "upstream": {"modelId": "google/siglip-base-patch16-224", "revision": "7fd15f0689c79d79e38b1c2e2e2370a7bf2761ed", "weightsSha256": UPSTREAM_WEIGHTS_SHA256},
        "runtime": {"onnxruntimeVersion": "1.20.1", "providers": ["CPUExecutionProvider"]},
        "contract": {"inputShape": [1, 3, 224, 224], "embeddingDimension": 768, "categoryOrder": ["human", "animal", "object", "other"]},
        "mathematics": {
            "preprocess": {"colorSpace": "RGB", "resize": {"height": 224, "width": 224, "resample": "bicubic"}, "rescale": 1.0 / 255.0, "normalize": {"mean": [0.5, 0.5, 0.5], "std": [0.5, 0.5, 0.5]}},
            "embeddingNormalization": "l2", "prototypeNormalization": "l2", "similarity": "normalized_dot_product",
            "logitScale": 1.0, "logitBias": 0.0, "prompts": PROMPTS, "promptCategoryIndices": CATEGORIES,
            "promptsSha256": prompt_contract_sha256(PROMPTS, CATEGORIES), "promptAggregation": "mean_logit_per_category_then_softmax",
        },
        "policy": {"subjectHintPolicyVersion": "subject-hint-policy-v2", "masterRankerVersion": "master-ranker-v2", "thresholds": {"highConfidence": 0.78, "margin": 0.18}},
        "files": {"vision_encoder.onnx": sha256(package / "vision_encoder.onnx"), "text_prototypes.npz": sha256(package / "text_prototypes.npz")},
    }


def create_package(tmp_path: Path) -> Path:
    package = tmp_path / ARTIFACT_PACKAGE_NAME
    package.mkdir(parents=True)
    (package / "vision_encoder.onnx").write_bytes(b"verified-onnx")
    np.savez(package / "text_prototypes.npz", embeddings=np.eye(4, 768, dtype=np.float32))
    (package / "manifest.json").write_text(json.dumps(manifest(package)), encoding="utf-8")
    return package


class _Node:
    def __init__(self, name: str, shape: tuple[int, ...]) -> None:
        self.name, self.shape = name, shape


def install_fake_runtime(monkeypatch, *, providers=("CPUExecutionProvider",), output_shape=(1, 768), version="1.20.1") -> None:
    class Session:
        def __init__(self, path: str, providers: list[str]) -> None:
            del path, providers

        def get_providers(self):
            return list(globals_providers)

        def get_inputs(self):
            return [_Node("pixel_values", (1, 3, 224, 224))]

        def get_outputs(self):
            return [_Node("embedding", output_shape)]

        def run(self, names, inputs):
            del names, inputs
            return [np.ones(output_shape, dtype=np.float32)]

    globals_providers = providers
    monkeypatch.setitem(sys.modules, "onnxruntime", types.SimpleNamespace(__version__=version, InferenceSession=Session))


def sample_image() -> bytes:
    image = Image.new("RGB", (32, 24), (120, 80, 40))
    result = BytesIO()
    image.save(result, format="PNG")
    return result.getvalue()


def test_siglip_onnx_contract_is_cpu_only_and_deterministic(tmp_path, monkeypatch):
    package = create_package(tmp_path)
    install_fake_runtime(monkeypatch)
    encoder = SiglipOnnxVisualEncoder(package)

    first, second = encoder.encode(sample_image()), encoder.encode(sample_image())
    assert first == second and len(first) == 768
    scores = encoder.classify(sample_image())
    assert tuple(scores) == ("human", "animal", "object", "other")
    assert sum(scores.values()) == pytest.approx(1.0)
    assert encoder.provenance()["upstreamRevision"] == "7fd15f0689c79d79e38b1c2e2e2370a7bf2761ed"


@pytest.mark.parametrize("filename", ["vision_encoder.onnx", "text_prototypes.npz"])
def test_siglip_onnx_rejects_checksum_tampering(tmp_path, monkeypatch, filename):
    package = create_package(tmp_path)
    install_fake_runtime(monkeypatch)
    with (package / filename).open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(VisualEncoderUnavailable, match="CHECKSUM_INVALID"):
        SiglipOnnxVisualEncoder(package)


def test_siglip_onnx_rejects_missing_artifact_file(tmp_path, monkeypatch):
    package = create_package(tmp_path)
    install_fake_runtime(monkeypatch)
    (package / "vision_encoder.onnx").unlink()
    with pytest.raises(VisualEncoderUnavailable, match="NOT_READY"):
        SiglipOnnxVisualEncoder(package)


def test_siglip_onnx_rejects_manifest_prompt_or_preprocess_tampering(tmp_path, monkeypatch):
    package = create_package(tmp_path)
    install_fake_runtime(monkeypatch)
    payload = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    payload["mathematics"]["prompts"][0] = "tampered prompt"
    (package / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(VisualEncoderUnavailable, match="MANIFEST_INVALID"):
        SiglipOnnxVisualEncoder(package)

    package = create_package(tmp_path / "preprocess")
    payload = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    payload["mathematics"]["preprocess"]["normalize"]["mean"] = [0.0, 0.0, 0.0]
    (package / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(VisualEncoderUnavailable, match="MANIFEST_INVALID"):
        SiglipOnnxVisualEncoder(package)


def test_siglip_onnx_rejects_a_manifest_with_an_unapproved_upstream_weight(tmp_path, monkeypatch):
    package = create_package(tmp_path)
    install_fake_runtime(monkeypatch)
    payload = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    payload["upstream"]["weightsSha256"] = "b" * 64
    (package / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(VisualEncoderUnavailable, match="MANIFEST_INVALID"):
        SiglipOnnxVisualEncoder(package)

def test_siglip_onnx_rejects_unexpected_provider_or_output_shape(tmp_path, monkeypatch):
    package = create_package(tmp_path)
    install_fake_runtime(monkeypatch, providers=("CUDAExecutionProvider",))
    with pytest.raises(VisualEncoderUnavailable, match="PROVIDER_INVALID"):
        SiglipOnnxVisualEncoder(package)

    install_fake_runtime(monkeypatch, output_shape=(1, 4))
    with pytest.raises(VisualEncoderUnavailable, match="OUTPUT_INVALID"):
        SiglipOnnxVisualEncoder(package)


def test_siglip_onnx_rejects_runtime_version_mismatch(tmp_path, monkeypatch):
    package = create_package(tmp_path)
    install_fake_runtime(monkeypatch, version="9.9.9")
    with pytest.raises(VisualEncoderUnavailable, match="RUNTIME_INCOMPATIBLE"):
        SiglipOnnxVisualEncoder(package)
