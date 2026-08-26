"""SAM 2.1 integration kept behind a small injectable boundary."""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO
from typing import Any

from PIL import Image

from modal_service.image_processing import AssetQualityCheck, normalize_segmented_asset

SAM_MODEL_ID = "facebook/sam2.1-hiera-small"
SAM_MODEL_REVISION = "e07df6aa19f5c6545121551bf89957b7663ee715"


class SegmentationError(RuntimeError):
    code = "SEGMENTATION_FAILED"


def segment_mascot(
    content: bytes,
    generator_factory: Callable[[], Any] | None = None,
) -> tuple[bytes, AssetQualityCheck]:
    """Select the dominant central SAM component and produce a validated RGBA asset."""
    with Image.open(BytesIO(content)) as source:
        image = source.convert("RGB")
    generator = (generator_factory or _load_generator)()
    result = generator(image, points_per_batch=32)
    mask = _select_central_mask(result, image.size)
    return normalize_segmented_asset(content, mask)


def _load_generator() -> Any:
    from transformers import pipeline

    return pipeline(
        task="mask-generation",
        model=SAM_MODEL_ID,
        revision=SAM_MODEL_REVISION,
        device=0,
    )


def _select_central_mask(result: Any, size: tuple[int, int]) -> Image.Image:
    masks = result.get("masks", []) if isinstance(result, dict) else []
    scores = result.get("scores", []) if isinstance(result, dict) else []
    candidates: list[tuple[float, Image.Image]] = []
    center_x, center_y = size[0] // 2, size[1] // 2
    for index, raw in enumerate(masks):
        mask = _as_mask(raw, size)
        bbox = mask.getbbox()
        if bbox is None or not (bbox[0] <= center_x <= bbox[2] and bbox[1] <= center_y <= bbox[3]):
            continue
        area = sum(mask.histogram()[128:]) / 255
        ratio = area / max(1, size[0] * size[1])
        if ratio < 0.03 or ratio > 0.85:
            continue
        score = float(scores[index]) if index < len(scores) else 1.0
        candidates.append((score * (1 - abs(ratio - 0.35)), mask))
    if not candidates:
        raise SegmentationError("SAM did not return a valid central subject mask.")
    return max(candidates, key=lambda item: item[0])[1]


def _as_mask(value: Any, size: tuple[int, int]) -> Image.Image:
    if isinstance(value, Image.Image):
        return value.convert("L").resize(size, Image.Resampling.NEAREST)
    try:
        import numpy as np

        array = np.asarray(value)
        if array.ndim > 2:
            array = array.squeeze()
        array = (array.astype("float32") > 0.5).astype("uint8") * 255
        return Image.fromarray(array, mode="L").resize(size, Image.Resampling.NEAREST)
    except Exception as error:
        raise SegmentationError("SAM returned an unsupported mask format.") from error
