"""Opt-in parity test for a controlled, non-Production export environment."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from modal_service.incubator import SiglipOnnxVisualEncoder


SOURCE_DIR = os.getenv("SIGLIP_PARITY_SOURCE_DIR")
ARTIFACT_DIR = os.getenv("SIGLIP_PARITY_ARTIFACT_DIR")
IMAGE_PATH = os.getenv("SIGLIP_PARITY_IMAGE")


@pytest.mark.skipif(not all((SOURCE_DIR, ARTIFACT_DIR, IMAGE_PATH)), reason="requires controlled local SigLIP source, artifact, and non-sensitive image")
def test_siglip_onnx_matches_pinned_transformers_embedding():
    import torch
    from PIL import Image
    from transformers import SiglipModel

    encoder = SiglipOnnxVisualEncoder(Path(str(ARTIFACT_DIR)))
    model = SiglipModel.from_pretrained(str(SOURCE_DIR), local_files_only=True).eval()
    with Image.open(str(IMAGE_PATH)) as source:
        image = source.convert("RGB").resize((224, 224), Image.Resampling.BICUBIC)
        values = np.asarray(image, dtype=np.float32) / 255.0
    values = (values - 0.5) / 0.5
    tensor = torch.from_numpy(np.ascontiguousarray(values.transpose(2, 0, 1)[None, ...]))
    with torch.inference_mode():
        expected = model.vision_model(pixel_values=tensor, return_dict=True).pooler_output[0].cpu().numpy()
    actual = np.asarray(encoder.encode(Path(str(IMAGE_PATH)).read_bytes()), dtype=np.float32)
    expected /= np.linalg.norm(expected)
    actual /= np.linalg.norm(actual)
    assert np.allclose(actual, expected, atol=1e-4, rtol=1e-4)
