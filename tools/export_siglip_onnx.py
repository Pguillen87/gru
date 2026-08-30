"""Offline exporter for the checksum-pinned SigLIP Incubator artifact.

It accepts only a pre-fetched local snapshot. It never downloads weights and
does not contact Modal. Run this in a controlled build environment, then have
the verifier approve the resulting directory before any Volume upload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


MODEL_ID = "google/siglip-base-patch16-224"
REVISION = "7fd15f0689c79d79e38b1c2e2e2370a7bf2761ed"
PACKAGE = "siglip-base-p16-224-zeroshot-v1"
ONNXRUNTIME_VERSION = "1.20.1"
UPSTREAM_WEIGHTS_SHA256 = "2c63cb7d1f2e95ba501893cbb8faeb4ea9a3af295498d35097126228659c2af8"
CATEGORY_ORDER = ("human", "animal", "object", "other")
PROMPTS = (
    "a photo of a person",
    "a photo of a human being",
    "a photo of an animal",
    "a photo of a dog",
    "a photo of a cat",
    "a photo of a bird",
    "a photo of an object",
    "a photo of a household object",
    "a photo of a device",
    "a photo of scenery",
    "a photo of a landscape",
    "a photo of food",
)
PROMPT_CATEGORIES = (0, 0, 1, 1, 1, 1, 2, 2, 2, 3, 3, 3)
PREPROCESS = {
    "colorSpace": "RGB",
    "resize": {"height": 224, "width": 224, "resample": "bicubic"},
    "rescale": 1.0 / 255.0,
    "normalize": {"mean": [0.5, 0.5, 0.5], "std": [0.5, 0.5, 0.5]},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prompt_sha256() -> str:
    payload = {"prompts": list(PROMPTS), "promptCategoryIndices": list(PROMPT_CATEGORIES), "categoryOrder": list(CATEGORY_ORDER)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def source_weights(source_dir: Path) -> Path:
    candidate = source_dir / "model.safetensors"
    if not candidate.is_file():
        raise SystemExit("Expected the pinned upstream model.safetensors in --source-dir.")
    return candidate


def export(source_dir: Path, output_dir: Path) -> dict[str, object]:
    import numpy as np
    import torch
    from transformers import AutoProcessor, SiglipModel

    if not source_dir.is_dir():
        raise SystemExit("--source-dir must be an already downloaded local snapshot.")
    weights = source_weights(source_dir)
    if sha256(weights) != UPSTREAM_WEIGHTS_SHA256:
        raise SystemExit("The local source weight SHA-256 does not match the approved upstream snapshot.")
    output_dir.mkdir(parents=True, exist_ok=False)
    model = SiglipModel.from_pretrained(source_dir, local_files_only=True).eval()
    processor = AutoProcessor.from_pretrained(source_dir, local_files_only=True)

    class VisionEncoder(torch.nn.Module):
        def __init__(self, source: SiglipModel) -> None:
            super().__init__()
            self.vision_model = source.vision_model

        def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
            return self.vision_model(pixel_values=pixel_values, return_dict=True).pooler_output

    vision = VisionEncoder(model).eval()
    target = output_dir / "vision_encoder.onnx"
    example = torch.zeros((1, 3, 224, 224), dtype=torch.float32)
    torch.onnx.export(
        vision,
        (example,),
        target,
        input_names=["pixel_values"],
        output_names=["embedding"],
        opset_version=17,
        dynamo=False,
    )
    with torch.inference_mode():
        text = processor.tokenizer(list(PROMPTS), padding="max_length", truncation=True, max_length=64, return_tensors="pt")
        embeddings = model.get_text_features(**text)
        embeddings = torch.nn.functional.normalize(embeddings, dim=-1).cpu().numpy().astype(np.float32)
    np.savez(output_dir / "text_prototypes.npz", embeddings=embeddings)
    logit_scale = float(model.logit_scale.exp().item())
    logit_bias = float(model.logit_bias.item())
    manifest = {
        "schemaVersion": 1,
        "artifact": {"package": PACKAGE, "encoderVersion": PACKAGE},
        "upstream": {"modelId": MODEL_ID, "revision": REVISION, "weightsSha256": UPSTREAM_WEIGHTS_SHA256, "license": "Apache-2.0"},
        "runtime": {"onnxruntimeVersion": ONNXRUNTIME_VERSION, "providers": ["CPUExecutionProvider"], "onnxOpset": 17},
        "contract": {"inputShape": [1, 3, 224, 224], "embeddingDimension": 768, "categoryOrder": list(CATEGORY_ORDER)},
        "mathematics": {
            "preprocess": PREPROCESS,
            "embeddingNormalization": "l2",
            "prototypeNormalization": "l2",
            "similarity": "normalized_dot_product",
            "logitScale": logit_scale,
            "logitBias": logit_bias,
            "prompts": list(PROMPTS),
            "promptCategoryIndices": list(PROMPT_CATEGORIES),
            "promptsSha256": prompt_sha256(),
            "promptAggregation": "mean_logit_per_category_then_softmax",
        },
        "policy": {"subjectHintPolicyVersion": "subject-hint-policy-v2", "masterRankerVersion": "master-ranker-v2", "thresholds": {"highConfidence": 0.78, "margin": 0.18}},
        "files": {"vision_encoder.onnx": sha256(target), "text_prototypes.npz": sha256(output_dir / "text_prototypes.npz")},
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(export(arguments.source_dir, arguments.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
