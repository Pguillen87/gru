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
MAX_INTERNAL_BACKGROUND_COMPONENT_PIXELS = 12
POSE_SET_VISUAL_QC_VERSION = "pose-set-visual-v2"
MAX_POSE_SCALE_DELTA = 0.12
MAX_POSE_WIDTH_DELTA = 0.12
MAX_POSE_OCCUPANCY_DELTA = 0.18
MAX_POSE_FOREGROUND_DELTA = 0.15
MAX_POSE_ASPECT_RATIO_DELTA = 0.20
MAX_POSE_CENTER_DELTA = 0.08
MAX_POSE_VERTICAL_CENTER_DELTA = 0.08
MAX_POSE_FOOT_BASE_DELTA = 0.04
MIN_POSE_FRAME_MARGIN = 0.02


def remove_connected_flat_background(content: bytes, threshold: int = 24, *, crop: bool = True) -> bytes:
    """Make a border-connected backdrop transparent without touching the subject."""
    with Image.open(BytesIO(content)) as source:
        image = source.convert("RGBA")
    if _has_editorial_pose_background(image):
        _remove_border_connected_editorial_background(image)
    else:
        _remove_flat_background_from_seeds(image, threshold)
    _remove_disconnected_alpha_noise(image)
    _remove_internal_editorial_background(image)
    if crop:
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
        and green - blue >= 12
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


def _remove_internal_editorial_background(image: Image.Image) -> None:
    """Remove enclosed editorial backdrop, including gaps inside a silhouette.

    Border flooding cannot reach the editorial colour between legs or an arm
    and torso. We remove only non-border-connected components matching the
    warm editorial palette; a chroma constraint excludes paper and subjects.
    """
    for start, _, touches_border in _editorial_background_components(image):
        if not touches_border:
            _clear_editorial_component(image, start)


def _is_editorial_background_residue(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return (
        # Includes the slightly darker floor/tapete residue emitted by the
        # template, while excluding white paper (low chroma) and skin (high
        # red-green separation).
        red >= 180
        and green >= 150
        and blue >= 100
        and red >= green >= blue
        and 0 <= red - green <= 45
        and 12 <= green - blue <= 70
    )


def _editorial_background_components(image: Image.Image) -> list[tuple[int, int, bool]]:
    """Return editorial-colour components as ``(start, size, touches_border)``."""
    width, height = image.size
    pixels = image.load()
    visited = bytearray(width * height)
    components: list[tuple[int, int, bool]] = []
    for start in range(width * height):
        if visited[start]:
            continue
        x, y = start % width, start // width
        red, green, blue, alpha = pixels[x, y]
        if alpha == 0 or not _is_editorial_background_residue((red, green, blue)):
            continue
        visited[start] = 1
        queue: deque[int] = deque([start])
        size = 0
        touches_border = False
        while queue:
            index = queue.popleft()
            current_x, current_y = index % width, index // width
            size += 1
            touches_border |= current_x in (0, width - 1) or current_y in (0, height - 1)
            for next_x, next_y in ((current_x - 1, current_y), (current_x + 1, current_y), (current_x, current_y - 1), (current_x, current_y + 1)):
                if not (0 <= next_x < width and 0 <= next_y < height):
                    continue
                next_index = next_y * width + next_x
                if visited[next_index]:
                    continue
                next_red, next_green, next_blue, next_alpha = pixels[next_x, next_y]
                if next_alpha == 0 or not _is_editorial_background_residue((next_red, next_green, next_blue)):
                    continue
                visited[next_index] = 1
                queue.append(next_index)
        components.append((start, size, touches_border))
    return components


def _clear_editorial_component(image: Image.Image, start: int) -> None:
    """Clear a known editorial component without thresholding subject colours."""
    width, height = image.size
    pixels = image.load()
    queue: deque[int] = deque([start])
    visited: set[int] = set()
    while queue:
        index = queue.popleft()
        if index in visited:
            continue
        visited.add(index)
        x, y = index % width, index // width
        red, green, blue, alpha = pixels[x, y]
        if alpha == 0 or not _is_editorial_background_residue((red, green, blue)):
            continue
        pixels[x, y] = (0, 0, 0, 0)
        for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= next_x < width and 0 <= next_y < height:
                queue.append(next_y * width + next_x)


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


def pose_set_visual_consistency_qc(poses: list[dict[str, object]]) -> dict[str, object]:
    """Fail closed on deterministic framing drift across the three pose assets.

    This gate deliberately does not try to score artistic quality. It rejects
    measurable regressions that make one pose look like a different camera:
    canvas drift, crop risk, scale/composition drift, a dominant scene and an
    inconsistent foot baseline. Semantic review remains a separate human gate.
    """
    required_roles = {"normal", "listening", "transcribing"}
    by_role = {str(pose.get("runtimeRole")): pose for pose in poses}
    reasons: list[str] = []
    if len(poses) != 3 or set(by_role) != required_roles:
        reasons.append("POSE_SET_ROLES_INVALID")
    metrics: list[dict[str, float]] = []
    dimensions: set[tuple[int, int]] = set()
    for role in sorted(required_roles):
        pose = by_role.get(role)
        qc = pose.get("qc") if isinstance(pose, dict) else None
        if not isinstance(qc, dict) or qc.get("status") != "passed":
            reasons.append("POSE_ALPHA_QC_REQUIRED")
            continue
        metric = _pose_visual_metrics(qc)
        if metric is None:
            reasons.append("POSE_FRAME_METADATA_INVALID")
            continue
        dimensions.add((int(qc["width"]), int(qc["height"])))
        metrics.append(metric)
    if len(dimensions) > 1:
        reasons.append("CANVAS_DIMENSIONS_MISMATCH")
    if len(metrics) == 3:
        if any(metric["top_margin"] < MIN_POSE_FRAME_MARGIN or metric["bottom_margin"] < MIN_POSE_FRAME_MARGIN for metric in metrics):
            reasons.append("FRAME_CROP_RISK")
        if _metric_delta(metrics, "height") > MAX_POSE_SCALE_DELTA:
            reasons.append("SCALE_MISMATCH")
        if _metric_delta(metrics, "width") > MAX_POSE_WIDTH_DELTA:
            reasons.append("SCALE_WIDTH_MISMATCH")
        if _metric_delta(metrics, "occupancy") > MAX_POSE_OCCUPANCY_DELTA:
            reasons.append("OCCUPANCY_MISMATCH")
        if _metric_delta(metrics, "aspect_ratio") > MAX_POSE_ASPECT_RATIO_DELTA:
            reasons.append("VISIBLE_PROPORTION_MISMATCH")
        if _metric_delta(metrics, "center_x") > MAX_POSE_CENTER_DELTA:
            reasons.append("CENTER_OFFSET_MISMATCH")
        if _metric_delta(metrics, "center_y") > MAX_POSE_VERTICAL_CENTER_DELTA:
            reasons.append("VERTICAL_CENTER_OFFSET_MISMATCH")
        if _metric_delta(metrics, "foot_base") > MAX_POSE_FOOT_BASE_DELTA:
            reasons.append("FOOT_BASE_MISMATCH")
        if _dominant_scene_detected(metrics):
            reasons.append("SCENE_DOMINANT")
    return {
        "status": "passed" if not reasons else "failed",
        "code": "VISUAL_POSE_CONSISTENCY_FAILED" if reasons else "VISUAL_POSE_CONSISTENCY_PASSED",
        "version": POSE_SET_VISUAL_QC_VERSION,
        "safe_reasons": sorted(set(reasons)),
    }


def _pose_visual_metrics(qc: dict[str, object]) -> dict[str, float] | None:
    """Extract normalized composition evidence from one technical-QC record."""
    try:
        width = int(qc["width"])
        height = int(qc["height"])
        left, top, right, bottom = (float(value) for value in qc["bounding_box"])
        foreground_ratio = float(qc["foreground_ratio"])
    except (KeyError, TypeError, ValueError):
        return None
    if (
        width < 1
        or height < 1
        or right <= left
        or bottom <= top
        or not 0 <= foreground_ratio <= 1
    ):
        return None
    relative_width = (right - left) / width
    relative_height = (bottom - top) / height
    return {
        "width": relative_width,
        "height": relative_height,
        "occupancy": relative_width * relative_height,
        "aspect_ratio": relative_width / relative_height,
        "foreground_ratio": foreground_ratio,
        "center_x": ((left + right) / 2) / width,
        "center_y": ((top + bottom) / 2) / height,
        "foot_base": bottom / height,
        "top_margin": top / height,
        "bottom_margin": (height - bottom) / height,
    }


def _metric_delta(metrics: list[dict[str, float]], key: str) -> float:
    values = [metric[key] for metric in metrics]
    return max(values) - min(values)


def _dominant_scene_detected(metrics: list[dict[str, float]]) -> bool:
    """Reject only a large composition takeover, not a small pose prop.

    A broad bounding box alone can be a legitimate gesture.  It becomes a
    scene signal only when the connected opaque area also grows materially.
    """
    return (
        _metric_delta(metrics, "occupancy") > MAX_POSE_OCCUPANCY_DELTA
        and _metric_delta(metrics, "foreground_ratio") > MAX_POSE_FOREGROUND_DELTA
    )


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
    internal_components = [
        size
        for _, size, touches_border in _editorial_background_components(image)
        if not touches_border and size > MAX_INTERNAL_BACKGROUND_COMPONENT_PIXELS
    ]
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
    if internal_components:
        reasons.append("INTERNAL_BACKGROUND_RESIDUE")
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
        "internal_background_components": len(internal_components),
        "internal_background_area": sum(internal_components),
        "largest_internal_background_component": max(internal_components, default=0),
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
