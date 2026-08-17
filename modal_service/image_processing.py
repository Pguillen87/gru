"""Deterministic post-processing for generated mascot artwork."""

from __future__ import annotations

from collections import deque
from io import BytesIO

from PIL import Image, ImageDraw


POSE_BACKGROUND = (241, 230, 201, 255)
POSE_CANVAS_SIZE = 1024


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


def normalize_pose_presentation(content: bytes) -> bytes:
    """Return a complete opaque pose canvas on Puleiro's editorial backdrop."""
    with Image.open(BytesIO(content)) as source:
        image = source.convert("RGBA")
    image = _remove_checkerboard_border(image)
    image = _crop_transparent_margin(image)
    image.thumbnail((int(POSE_CANVAS_SIZE * 0.8), int(POSE_CANVAS_SIZE * 0.8)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (POSE_CANVAS_SIZE, POSE_CANVAS_SIZE), POSE_BACKGROUND)
    offset = ((POSE_CANVAS_SIZE - image.width) // 2, (POSE_CANVAS_SIZE - image.height) // 2)
    canvas.alpha_composite(image, offset)
    output = BytesIO()
    canvas.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()


def _remove_checkerboard_border(image: Image.Image) -> Image.Image:
    """Erase neutral border-connected grid pixels while retaining the central subject."""
    width, height = image.size
    pixels = image.load()
    visited: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        queue.extend(((x, 0), (x, height - 1)))
    for y in range(height):
        queue.extend(((0, y), (width - 1, y)))
    while queue:
        x, y = queue.popleft()
        if (x, y) in visited:
            continue
        visited.add((x, y))
        red, green, blue, alpha = pixels[x, y]
        if alpha == 0 or not _is_neutral_background(red, green, blue):
            continue
        pixels[x, y] = (0, 0, 0, 0)
        for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= next_x < width and 0 <= next_y < height and (next_x, next_y) not in visited:
                queue.append((next_x, next_y))
    return image


def _is_neutral_background(red: int, green: int, blue: int) -> bool:
    return max(red, green, blue) - min(red, green, blue) <= 18


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
