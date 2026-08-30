"""Verify a SigLIP ONNX artifact against the local pinned Transformers source."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--atol", type=float, default=1e-4)
    parser.add_argument("--rtol", type=float, default=1e-4)
    arguments = parser.parse_args()
    import numpy as np
    import torch
    from PIL import Image
    from transformers import SiglipModel
    from modal_service.incubator import SiglipOnnxVisualEncoder

    encoder = SiglipOnnxVisualEncoder(arguments.artifact_dir)
    model = SiglipModel.from_pretrained(arguments.source_dir, local_files_only=True).eval()
    with Image.open(arguments.image) as source:
        image = source.convert("RGB").resize((224, 224), Image.Resampling.BICUBIC)
        pixel_values = np.asarray(image, dtype=np.float32) / 255.0
    pixel_values = (pixel_values - 0.5) / 0.5
    input_tensor = torch.from_numpy(np.ascontiguousarray(pixel_values.transpose(2, 0, 1)[None, ...]))
    with torch.inference_mode():
        expected = model.vision_model(pixel_values=input_tensor, return_dict=True).pooler_output[0].cpu().numpy()
    actual = np.asarray(encoder.encode(arguments.image.read_bytes()), dtype=np.float32)
    expected /= np.linalg.norm(expected)
    actual /= np.linalg.norm(actual)
    report = {"embeddingDimension": int(actual.shape[0]), "maxAbsError": float(np.max(np.abs(actual - expected))), "withinTolerance": bool(np.allclose(actual, expected, atol=arguments.atol, rtol=arguments.rtol)), "provenance": encoder.provenance()}
    print(json.dumps(report, sort_keys=True))
    if not report["withinTolerance"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
