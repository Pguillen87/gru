import base64
from io import BytesIO

from PIL import Image

from modal_service.image_processing import strip_image_metadata
from modal_service.validation import validate_image
from modal_service.web_v2 import prepare_web_v2_upload


def jpeg_upload() -> bytes:
    output = BytesIO()
    Image.new("RGB", (512, 512), "white").save(output, format="JPEG")
    return output.getvalue()


def test_web_v2_accepts_a_jpeg_after_privacy_scrub_reencodes_it_as_png():
    source = jpeg_upload()
    sanitized = prepare_web_v2_upload(
        base64.b64encode(source).decode("ascii"),
        "image/jpeg",
        lambda value: base64.b64decode(value, validate=True),
        validate_image,
        strip_image_metadata,
    )

    assert validate_image(sanitized) == ("PNG", 512, 512)
