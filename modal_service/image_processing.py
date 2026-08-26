"""Deterministic segmentation output normalization and asset quality checks."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter

CANVAS_SIZE = 1024
SAFE_MARGIN_RATIO = 0.08


@dataclass(frozen=True)
class AssetQualityCheck:
    status: str
    safe_reasons: tuple[str, ...]
    alpha_ratio: float
    border_opaque_ratio: float
    foreground_components: int
    width: int
    height: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class AssetQualityError(ValueError):
    code = "ASSET_QC_FAILED"

    def __init__(self, check: AssetQualityCheck) -> None:
        super().__init__(", ".join(check.safe_reasons) or "Asset quality validation failed.")
        self.check = check


def strip_image_metadata(content: bytes) -> bytes:
    """Re-encode an upload as PNG so EXIF/GPS and ancillary metadata are not retained."""
    with Image.open(BytesIO(content)) as source:
        image = source.convert("RGBA")
    return _encode_png(image)


def normalize_segmented_asset(content: bytes, mask: Image.Image) -> tuple[bytes, AssetQualityCheck]:
    """Apply a real segmentation mask and place the subject on a canonical transparent canvas."""
    with Image.open(BytesIO(content)) as source:
        artwork = source.convert("RGBA")
    binary = _central_component_mask(mask.convert("L").resize(artwork.size, Image.Resampling.BILINEAR))
    if binary.getbbox() is None:
        check = AssetQualityCheck("failed", ("EMPTY_FOREGROUND",), 1.0, 0.0, 0, CANVAS_SIZE, CANVAS_SIZE)
        raise AssetQualityError(check)
    feathered = binary.filter(ImageFilter.GaussianBlur(radius=max(1.25, max(artwork.size) / 700)))
    artwork.putalpha(feathered)
    canvas = _fit_on_canvas(artwork)
    encoded = _encode_png(canvas)
    check = inspect_asset(encoded)
    if check.status != "passed":
        raise AssetQualityError(check)
    return encoded, check


def inspect_asset(content: bytes) -> AssetQualityCheck:
    """Return safe numeric QC metrics without retaining image or biometric content."""
    try:
        with Image.open(BytesIO(content)) as source:
            image = source.convert("RGBA")
    except Exception as error:
        raise AssetQualityError(AssetQualityCheck("failed", ("INVALID_RGBA",), 0, 1, 0, 0, 0)) from error
    alpha = image.getchannel("A")
    histogram = alpha.histogram()
    pixels = max(1, image.width * image.height)
    transparent_ratio = sum(histogram[:8]) / pixels
    intermediate = sum(histogram[8:248])
    border = _border_values(alpha)
    border_opaque = sum(value >= 8 for value in border) / max(1, len(border))
    components = _component_count(alpha)
    reasons: list[str] = []
    if image.mode != "RGBA" or image.size != (CANVAS_SIZE, CANVAS_SIZE):
        reasons.append("INVALID_RGBA_CANVAS")
    if transparent_ratio < 0.10:
        reasons.append("BACKGROUND_NOT_TRANSPARENT")
    if border_opaque > 0:
        reasons.append("FOREGROUND_TOUCHES_BORDER")
    if intermediate == 0:
        reasons.append("HARD_ALPHA_EDGE")
    if components != 1:
        reasons.append("DISCONNECTED_FOREGROUND")
    bbox = alpha.point(lambda value: 255 if value >= 8 else 0).getbbox()
    margin = int(CANVAS_SIZE * SAFE_MARGIN_RATIO)
    if bbox is None:
        reasons.append("EMPTY_FOREGROUND")
    elif bbox[0] < margin or bbox[1] < margin or bbox[2] > CANVAS_SIZE - margin or bbox[3] > CANVAS_SIZE - margin:
        reasons.append("INSUFFICIENT_SAFE_MARGIN")
    return AssetQualityCheck(
        "passed" if not reasons else "failed", tuple(reasons), round(transparent_ratio, 6),
        round(border_opaque, 6), components, image.width, image.height,
    )


def remove_connected_flat_background(content: bytes, threshold: int = 24) -> bytes:
    """Legacy V1 helper retained for Android compatibility; V2 uses SAM segmentation."""
    with Image.open(BytesIO(content)) as source:
        image = source.convert("RGBA")
    width, height = image.size
    for seed in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1),
                 (width // 2, 0), (width // 2, height - 1), (0, height // 2), (width - 1, height // 2)):
        if image.getpixel(seed)[3] != 0:
            ImageDraw.floodfill(image, seed, (0, 0, 0, 0), thresh=threshold)
    bbox = image.getbbox()
    if bbox:
        left, top, right, bottom = bbox
        padding = max(8, int(max(right - left, bottom - top) * 0.06))
        image = image.crop((max(0, left-padding), max(0, top-padding), min(width, right+padding), min(height, bottom+padding)))
    return _encode_png(image)


def transparency_ratio(content: bytes) -> float:
    return inspect_asset(content).alpha_ratio


def _fit_on_canvas(image: Image.Image) -> Image.Image:
    bbox = image.getchannel("A").point(lambda value: 255 if value >= 8 else 0).getbbox()
    if bbox is None:
        return Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    subject = image.crop(bbox)
    available = int(CANVAS_SIZE * (1 - SAFE_MARGIN_RATIO * 2))
    subject.thumbnail((available, available), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    x = (CANVAS_SIZE - subject.width) // 2
    y = (CANVAS_SIZE - subject.height) // 2
    canvas.alpha_composite(subject, (x, y))
    return canvas


def _central_component_mask(mask: Image.Image) -> Image.Image:
    sample = mask.resize((256, 256), Image.Resampling.BILINEAR).point(lambda value: 255 if value >= 128 else 0)
    pixels = sample.load()
    visited: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for y in range(sample.height):
        for x in range(sample.width):
            if pixels[x, y] == 0 or (x, y) in visited:
                continue
            component: list[tuple[int, int]] = []
            queue = deque([(x, y)])
            visited.add((x, y))
            while queue:
                point = queue.popleft()
                component.append(point)
                px, py = point
                for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                    if 0 <= nx < 256 and 0 <= ny < 256 and pixels[nx, ny] and (nx, ny) not in visited:
                        visited.add((nx, ny)); queue.append((nx, ny))
            components.append(component)
    if not components:
        return Image.new("L", mask.size, 0)
    center = (127.5, 127.5)
    chosen = min(
        components,
        key=lambda points: (-len(points), min((x-center[0])**2 + (y-center[1])**2 for x, y in points)),
    )
    result = Image.new("L", (256, 256), 0)
    output = result.load()
    for x, y in chosen:
        output[x, y] = 255
    return result.resize(mask.size, Image.Resampling.NEAREST)


def _component_count(alpha: Image.Image) -> int:
    sample = alpha.resize((128, 128), Image.Resampling.BILINEAR).point(lambda value: 255 if value >= 32 else 0)
    pixels = sample.load(); visited: set[tuple[int, int]] = set(); count = 0
    for y in range(128):
        for x in range(128):
            if not pixels[x, y] or (x, y) in visited:
                continue
            count += 1; queue = deque([(x, y)]); visited.add((x, y))
            while queue:
                px, py = queue.popleft()
                for nx, ny in ((px-1, py),(px+1, py),(px,py-1),(px,py+1)):
                    if 0 <= nx < 128 and 0 <= ny < 128 and pixels[nx, ny] and (nx, ny) not in visited:
                        visited.add((nx, ny)); queue.append((nx, ny))
    return count


def _border_values(alpha: Image.Image) -> list[int]:
    values = list(alpha.getdata())
    width, height = alpha.size
    return values[:width] + values[-width:] + values[::width] + values[width-1::width]


def _encode_png(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
