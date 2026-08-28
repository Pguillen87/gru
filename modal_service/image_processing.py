"""Deterministic post-processing for generated mascot artwork."""

from __future__ import annotations

from collections import deque
import hashlib
from io import BytesIO

from PIL import Image, ImageDraw


POSE_BACKGROUND = (241, 230, 201, 255)
POSE_CANVAS_SIZE = 1024
MIN_MASTER_ALPHA_RATIO = 0.01
MAX_MASTER_BORDER_OPAQUE_RATIO = 0.02
MIN_FOREGROUND_RATIO = 0.005
ALPHA_COMPONENT_THRESHOLD = 16
MAX_DISCONNECTED_NOISE_RATIO = 0.0001
MAX_HALO_RISK_RATIO = 0.02


def remove_connected_flat_background(content: bytes, threshold: int = 24) -> bytes:
    """Make a border-connected backdrop transparent without touching the subject."""
    with Image.open(BytesIO(content)) as source:
        image = source.convert("RGBA")
    if _has_editorial_pose_background(image):
        _remove_border_connected_editorial_background(image)
    else:
        _remove_flat_background_from_seeds(image, threshold)
    _remove_disconnected_alpha_noise(image)
    _remove_editorial_background_islands(image)
    image = _crop_transparent_margin(image)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _remove_flat_background_from_seeds(image: Image.Image, threshold: int) -> None:
    """Retain the legacy flat-colour path for non-editorial Master backdrops."""
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


def _has_editorial_pose_background(image: Image.Image) -> bool:
    """Detect the pale editorial backdrop without treating border-touching skin as background."""
    width, height = image.size
    border_pixels = [
        image.getpixel((x, y))
        for x, y in _border_coordinates(width, height)
    ]
    editorial = sum(_is_editorial_pose_background(pixel) for pixel in border_pixels)
    return editorial / max(1, len(border_pixels)) >= 0.35


def _remove_border_connected_editorial_background(image: Image.Image) -> None:
    """Flood only pale editorial pixels connected to the canvas edge.

    Generated poses can touch an edge with a hand or shirt.  Seeding every edge
    pixel would erase those details, so only pixels matching the known backdrop
    palette may enter the flood fill.
    """
    width, height = image.size
    pixels = image.load()
    visited = bytearray(width * height)
    queue: deque[int] = deque()
    for x, y in _border_coordinates(width, height):
        if _is_editorial_pose_background(pixels[x, y]):
            queue.append(y * width + x)
    while queue:
        index = queue.popleft()
        if visited[index]:
            continue
        visited[index] = 1
        x, y = index % width, index // width
        if not _is_editorial_pose_background(pixels[x, y]):
            continue
        pixels[x, y] = (0, 0, 0, 0)
        for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= next_x < width and 0 <= next_y < height:
                next_index = next_y * width + next_x
                if not visited[next_index]:
                    queue.append(next_index)


def _is_editorial_pose_background(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    return (
        alpha > 0
        and red >= 220
        and green >= 210
        and blue >= 185
        and red - green <= 50
        and green - blue <= 45
    )


def _border_coordinates(width: int, height: int):
    for x in range(width):
        yield x, 0
        yield x, height - 1
    for y in range(1, max(1, height - 1)):
        yield 0, y
        yield width - 1, y


def _remove_disconnected_alpha_noise(image: Image.Image) -> None:
    """Remove only tiny detached alpha islands; preserve intentional accessories."""
    alpha = image.getchannel("A")
    pixels = image.load()
    for size, component in _alpha_components_with_pixels(alpha, image.width, image.height, retain_limit=12):
        if size > 12 or component is None:
            continue
        for index in component:
            x, y = index % image.width, index // image.width
            pixels[x, y] = (0, 0, 0, 0)


def _remove_editorial_background_islands(image: Image.Image) -> None:
    """Remove small detached remnants of the editorial backdrop.

    The model occasionally leaves cream floor flecks near shoes.  They are not
    connected to the subject and are distinct from intentional props such as a
    table or chair, which use non-editorial colours or join the main component.
    """
    alpha = image.getchannel("A")
    pixels = image.load()
    for size, component in _alpha_components_with_pixels(alpha, image.width, image.height, retain_limit=1024):
        if size > 1024 or component is None:
            continue
        average = tuple(
            sum(pixels[index % image.width, index // image.width][channel] for index in component) // len(component)
            for channel in range(3)
        )
        if not _is_editorial_background_residue(average):
            continue
        for index in component:
            x, y = index % image.width, index // image.width
            pixels[x, y] = (0, 0, 0, 0)


def _is_editorial_background_residue(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return red >= 210 and green >= 200 and blue >= 165 and red - green <= 45 and green - blue <= 55


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
    subject = image.crop((left, top, right, bottom))
    canvas = Image.new("RGBA", (subject.width + 2 * padding, subject.height + 2 * padding))
    canvas.alpha_composite(subject, (padding, padding))
    return canvas


def transparency_ratio(content: bytes) -> float:
    with Image.open(BytesIO(content)) as image:
        alpha = image.convert("RGBA").getchannel("A")
        histogram = alpha.histogram()
    return sum(histogram[:250]) / max(1, image.width * image.height)


def master_transparency_qc(content: bytes) -> dict[str, object]:
    """Validate a derived Master without ever changing its source artifact."""
    return transparent_asset_qc(content, asset_kind="master")


def pose_transparency_qc(content: bytes) -> dict[str, object]:
    """Validate a derived pose before it is promoted to the private set."""
    return transparent_asset_qc(content, asset_kind="pose")


def transparent_asset_qc(content: bytes, *, asset_kind: str) -> dict[str, object]:
    """Return only safe, reproducible quality evidence for an RGBA derivative."""
    with Image.open(BytesIO(content)) as source:
        source_format = source.format
        source_mode = source.mode
        image = source.convert("RGBA")
    width, height = image.size
    alpha = image.getchannel("A")
    histogram = alpha.histogram()
    total = max(1, width * height)
    transparent_ratio_value = histogram[0] / total
    semi_transparent_ratio = sum(histogram[1:255]) / total
    alpha_ratio = sum(histogram[:250]) / total
    border = []
    for x in range(width):
        border.extend((alpha.getpixel((x, 0)), alpha.getpixel((x, height - 1))))
    for y in range(1, max(1, height - 1)):
        border.extend((alpha.getpixel((0, y)), alpha.getpixel((width - 1, y))))
    border_opaque_ratio = sum(value >= 250 for value in border) / max(1, len(border))
    components = _alpha_components(alpha, width, height)
    noise_pixels = sum(component for component in components[1:] if component <= 12)
    foreground_ratio = (components[0] if components else 0) / total
    halo_risk_ratio = _halo_risk_ratio(image, alpha)
    reasons: list[str] = []
    if source_format != "PNG" or source_mode != "RGBA":
        reasons.append("RGBA_PNG_REQUIRED")
    if alpha_ratio < MIN_MASTER_ALPHA_RATIO:
        reasons.append("ALPHA_INSUFFICIENT")
    if foreground_ratio < MIN_FOREGROUND_RATIO:
        reasons.append("FOREGROUND_EMPTY")
    if border_opaque_ratio > MAX_MASTER_BORDER_OPAQUE_RATIO:
        reasons.append("BACKGROUND_CONNECTED_TO_BORDER")
    if noise_pixels / total > MAX_DISCONNECTED_NOISE_RATIO:
        reasons.append("DISCONNECTED_NOISE")
    if halo_risk_ratio > MAX_HALO_RISK_RATIO:
        reasons.append("HALO_RISK")
    return {
        "status": "passed" if not reasons else "failed",
        "safe_reasons": reasons,
        "asset_kind": asset_kind,
        "sha256": hashlib.sha256(content).hexdigest(),
        "format": source_format,
        "mode": source_mode,
        "alpha_ratio": round(alpha_ratio, 6),
        "transparent_ratio": round(transparent_ratio_value, 6),
        "semi_transparent_ratio": round(semi_transparent_ratio, 6),
        "border_opaque_ratio": round(border_opaque_ratio, 6),
        "bounding_box": list(alpha.getbbox() or (0, 0, 0, 0)),
        "component_count": len(components),
        "largest_component_pixels": components[0] if components else 0,
        "foreground_ratio": round(foreground_ratio, 6),
        "disconnected_noise_pixels": noise_pixels,
        "halo_risk_ratio": round(halo_risk_ratio, 6),
        "width": width,
        "height": height,
    }


def _alpha_components(alpha: Image.Image, width: int, height: int) -> list[int]:
    return sorted((size for size, _ in _alpha_components_with_pixels(alpha, width, height, retain_limit=0)), reverse=True)


def _alpha_components_with_pixels(
    alpha: Image.Image,
    width: int,
    height: int,
    *,
    retain_limit: int,
) -> list[tuple[int, list[int] | None]]:
    """Count all components while retaining pixels only for small candidates."""
    pixels = alpha.load()
    visited = bytearray(width * height)
    components: list[tuple[int, list[int] | None]] = []
    for start in range(width * height):
        if visited[start] or pixels[start % width, start // width] < ALPHA_COMPONENT_THRESHOLD:
            continue
        visited[start] = 1
        queue = deque([start])
        component: list[int] | None = [] if retain_limit else None
        size = 0
        while queue:
            index = queue.popleft()
            size += 1
            if component is not None:
                if size <= retain_limit:
                    component.append(index)
                else:
                    component = None
            x, y = index % width, index // width
            for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if not (0 <= next_x < width and 0 <= next_y < height):
                    continue
                next_index = next_y * width + next_x
                if visited[next_index] or pixels[next_x, next_y] < ALPHA_COMPONENT_THRESHOLD:
                    continue
                visited[next_index] = 1
                queue.append(next_index)
        components.append((size, component))
    return components


def _halo_risk_ratio(image: Image.Image, alpha: Image.Image) -> float:
    """Flag pale semi-transparent fringes without guessing a hidden backdrop."""
    pixels = image.load()
    alpha_pixels = alpha.load()
    risky = 0
    sampled = 0
    for y in range(image.height):
        for x in range(image.width):
            value = alpha_pixels[x, y]
            if not 1 <= value < 255:
                continue
            sampled += 1
            red, green, blue, _ = pixels[x, y]
            if min(red, green, blue) >= 220 and max(red, green, blue) - min(red, green, blue) <= 18:
                risky += 1
    return risky / max(1, sampled)
