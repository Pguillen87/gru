from io import BytesIO

import pytest
from PIL import Image

from modal_service.validation import ImageValidationError, validate_image


def png(width=512, height=512) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), "white").save(output, format="PNG")
    return output.getvalue()


def test_valid_image_uses_real_format_and_dimensions():
    assert validate_image(png(), "image/png") == ("PNG", 512, 512)


@pytest.mark.parametrize("content", [b"", b"not-an-image"])
def test_empty_or_corrupt_image_is_rejected(content):
    with pytest.raises(ImageValidationError):
        validate_image(content)


def test_mime_mismatch_and_extreme_dimensions_are_rejected():
    with pytest.raises(ImageValidationError):
        validate_image(png(), "image/jpeg")
    with pytest.raises(ImageValidationError):
        validate_image(png(128, 512), "image/png")
