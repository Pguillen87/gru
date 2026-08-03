"""Byte-level image validation before any GPU work is scheduled."""

from __future__ import annotations

from io import BytesIO


ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_BYTES = 10 * 1024 * 1024
MIN_SIDE = 256
MAX_SIDE = 4096


class ImageValidationError(ValueError):
    code = "INVALID_IMAGE"


def validate_image(content: bytes, declared_content_type: str | None = None) -> tuple[str, int, int]:
    from PIL import Image, UnidentifiedImageError

    if not content or len(content) > MAX_BYTES:
        raise ImageValidationError("Image size is invalid.")
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            image.load()
            actual_format = image.format or ""
            width, height = image.size
    except (UnidentifiedImageError, OSError) as error:
        raise ImageValidationError("Image cannot be decoded.") from error
    if actual_format not in ALLOWED_FORMATS:
        raise ImageValidationError("Unsupported image format.")
    if min(width, height) < MIN_SIDE or max(width, height) > MAX_SIDE:
        raise ImageValidationError("Image dimensions are outside the supported range.")
    if declared_content_type and actual_format.lower() not in declared_content_type.lower():
        raise ImageValidationError("Declared MIME type does not match image content.")
    return actual_format, width, height
