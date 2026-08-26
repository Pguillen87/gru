from io import BytesIO

from PIL import Image

from modal_service.image_processing import (
    inspect_asset, normalize_segmented_asset, remove_connected_flat_background,
    strip_image_metadata, transparency_ratio,
)


def test_flat_border_background_becomes_transparent_without_erasing_subject():
    image = Image.new("RGB", (64, 64), (235, 231, 222))
    for x in range(20, 44):
        for y in range(16, 56):
            image.putpixel((x, y), (120, 55, 30))
    source = BytesIO()
    image.save(source, format="PNG")

    normalized = remove_connected_flat_background(source.getvalue())
    result = Image.open(BytesIO(normalized)).convert("RGBA")

    assert result.getpixel((0, 0))[3] == 0
    assert result.width < 64
    assert result.height < 64
    assert result.getchannel("A").getbbox() is not None
    assert transparency_ratio(normalized) > 0.1


def test_upload_is_reencoded_without_exif_metadata():
    image = Image.new("RGB", (256, 256), "white")
    source = BytesIO()
    image.save(source, format="JPEG", exif=b"Exif\x00\x00test-metadata")

    sanitized = Image.open(BytesIO(strip_image_metadata(source.getvalue())))

    assert sanitized.format == "PNG"
    assert not sanitized.getexif()


def test_segmented_asset_has_real_soft_alpha_and_safe_margin():
    image = Image.new("RGB", (128, 192), (240, 240, 240))
    mask = Image.new("L", image.size, 0)
    for x in range(36, 92):
        for y in range(24, 170):
            mask.putpixel((x, y), 255)
    source = BytesIO(); image.save(source, "PNG")

    normalized, check = normalize_segmented_asset(source.getvalue(), mask)
    result = Image.open(BytesIO(normalized))

    assert result.mode == "RGBA"
    assert result.size == (1024, 1024)
    assert check.status == "passed"
    assert check.border_opaque_ratio == 0
    assert any(0 < value < 255 for value in result.getchannel("A").getdata())
    assert inspect_asset(normalized).safe_reasons == ()
