"""Deterministic post-processing for generated mascot artwork."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw


def remove_connected_flat_background(content: bytes, threshold: int = 24) -> bytes:
    """Make a flat border-connected background transparent without touching islands."""
    with Image.open(BytesIO(content)) as source:
        image = source.convert("RGBA")
    width, height = image.size
    seeds = (
        (0, 0),
        (width - 1, 0),
        (0, height - 1),
        (width - 1, height - 1),
        (width // 2, 0),
        (width // 2, height - 1),
        (0, height // 2),
        (width - 1, height // 2),
    )
    for seed in seeds:
        if image.getpixel(seed)[3] != 0:
            ImageDraw.floodfill(image, seed, (0, 0, 0, 0), thresh=threshold)
    image = _crop_transparent_margin(image)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _crop_transparent_margin(image: Image.Image) -> Image.Image:
    bbox = image.getbbox()
    if bbox is None:
        return image
    left, top, right, bottom = bbox
    padding = max(8, int(max(right - left, bottom - top) * 0.06))
    return image.crop((
        max(0, left - padding),
        max(0, top - padding),
        min(image.width, right + padding),
        min(image.height, bottom + padding),
    ))


def transparency_ratio(content: bytes) -> float:
    with Image.open(BytesIO(content)) as image:
        alpha = image.convert("RGBA").getchannel("A")
        histogram = alpha.histogram()
    return sum(histogram[:250]) / max(1, image.width * image.height)
